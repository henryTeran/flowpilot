"""Exact reorder and explicit recipe-volume scenarios. Never changes stock/orders."""
from sqlalchemy import func, select
from app.modules.inventory import service as stock
from app.modules.inventory.models import StockItem, StockMovement, StockPurchaseOrderLine, StockPurchaseReceiptLine, StockRecipe, StockRecipeLine
from app.modules.inventory.outlook_schemas import DemandRead, OutlookItem, OutlookRead
from app.modules.services.models import Service
from app.shared.exceptions import not_found, business_error
from app.shared.time import utcnow


def quantity(milli):
    # Python integers preserve large aggregates, independent of Decimal context.
    return f"{milli // 1000}.{milli % 1000:03d}"


def selected_demand(db, institute, scenario):
    if scenario is None:
        return [], {}, True
    service_ids = [row.service_id for row in scenario.demands]
    services = {row.id: row for row in db.scalars(select(Service).where(Service.id.in_(service_ids)))}
    recipe_ids = [row.recipe_id for row in scenario.demands if row.recipe_id is not None]
    recipes = {row.id: row for row in db.scalars(select(StockRecipe).where(
        StockRecipe.institute_id == institute, StockRecipe.id.in_(recipe_ids)))} if recipe_ids else {}
    lines = db.scalars(select(StockRecipeLine).where(StockRecipeLine.institute_id == institute,
        StockRecipeLine.recipe_id.in_(recipe_ids))).all() if recipe_ids else []
    multipliers, demands, complete = {}, [], True
    for row in scenario.demands:
        service = services.get(row.service_id)
        if service is None:
            raise not_found("Prestation du scenario introuvable")
        recipe = recipes.get(row.recipe_id)
        if row.recipe_id is not None and (recipe is None or recipe.service_id != row.service_id):
            raise not_found("Version de recette du scenario introuvable")
        state = "missing_selected_norm" if recipe is None else "enabled" if recipe.enabled else "disabled"
        complete = complete and recipe is not None
        if recipe is not None and recipe.enabled:
            multipliers[recipe.id] = row.quantity
        demands.append(DemandRead(**row.model_dump(), service_name=service.name,
            recipe_revision=recipe.revision if recipe else None, state=state))
    known = {}
    for line in lines:
        known[line.item_id] = known.get(line.item_id, 0) + line.quantity_milli * multipliers.get(line.recipe_id, 0)
    return demands, known, complete


def pending_quantities(db, institute, item_ids):
    if not item_ids:
        return {}
    received = select(StockPurchaseReceiptLine.order_id, StockPurchaseReceiptLine.item_id,
        func.sum(StockPurchaseReceiptLine.quantity_milli).label("amount")).where(
        StockPurchaseReceiptLine.institute_id == institute, StockPurchaseReceiptLine.item_id.in_(item_ids)
    ).group_by(StockPurchaseReceiptLine.order_id, StockPurchaseReceiptLine.item_id).subquery()
    lines = StockPurchaseOrderLine
    query = select(lines.item_id, lines.quantity_milli, func.coalesce(received.c.amount, 0)).outerjoin(
        received, (received.c.order_id == lines.order_id) & (received.c.item_id == lines.item_id)
    ).where(lines.institute_id == institute, lines.item_id.in_(item_ids))
    pending = {}
    # Per-order receipt sums stay within the original order's exact quantity.
    # Stream ordered rows and aggregate in Python, avoiding SQL sum overflow or float casts.
    for item_id, ordered, delivered in db.execute(query).yield_per(200):
        remaining = int(ordered) - int(delivered)
        if remaining < 0:
            raise business_error("Les receptions depassent la commande originale")
        pending[item_id] = pending.get(item_id, 0) + remaining
    return pending


def read(db, institute, limit, offset, scenario=None):
    stock.lock_institute(db, institute)  # Same serialization boundary as all stock/recipe/order writers.
    demands, known, complete = selected_demand(db, institute, scenario)
    items = db.scalars(select(StockItem).where(StockItem.institute_id == institute)
        .order_by(StockItem.sku, StockItem.id).limit(limit).offset(offset)).all()
    ids = [row.id for row in items]
    balances = dict(db.execute(select(StockMovement.item_id, func.sum(StockMovement.quantity_milli)).where(
        StockMovement.institute_id == institute, StockMovement.item_id.in_(ids)).group_by(StockMovement.item_id)).all()) if ids else {}
    pending = pending_quantities(db, institute, ids)
    rows = []
    for item in items:
        balance, demand, ordered = int(balances.get(item.id, 0)), known.get(item.id, 0), pending.get(item.id, 0)
        if not 0 <= balance <= stock.MAX_MILLI:
            raise business_error("Solde de stock a verifier")
        rows.append(OutlookItem(item_id=item.id, item_sku=item.sku, item_name=item.name,
            category=item.category, unit=item.unit, on_hand=quantity(balance), threshold=quantity(item.reorder_milli),
            at_or_below_threshold=balance <= item.reorder_milli,
            threshold_shortfall=quantity(max(0, item.reorder_milli - balance)),
            pending_order_quantity=quantity(ordered), known_demand=quantity(demand),
            complete_demand=quantity(demand) if scenario is not None and complete else None,
            known_demand_shortfall=quantity(max(0, demand + item.reorder_milli - balance)),
            conditional_shortfall_after_all_orders=quantity(max(0, demand + item.reorder_milli - balance - ordered))))
    return OutlookRead(institute_id=institute, generated_at=utcnow(),
        starts_at=scenario.starts_at if scenario else None, ends_at=scenario.ends_at if scenario else None,
        source="explicit_service_volume_scenario" if scenario else "recorded_stock",
        coverage=("complete_selected_norms" if complete else "partial_selected_norms") if scenario else "not_applicable",
        demands=demands, limit=limit, offset=offset, items=rows)
