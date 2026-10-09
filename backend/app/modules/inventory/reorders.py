"""Retained source-backed reorder proposals; never creates orders or movements."""
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, StringConstraints, model_validator, field_validator
from sqlalchemy import select
from app.modules.crm.metrics import Fact
from app.modules.base.read_capabilities import ExactId, Digest, Actor
from app.modules.base.plans import Reason, Key
from app.modules.inventory import outlook, suppliers, service as stock
from app.modules.inventory.outlook_schemas import ForecastScenario, ScenarioDemand
from app.modules.inventory.models import StockReorderOriginal
from app.modules.waitlist.originals import fingerprint, Envelope
from app.shared.time import utcnow, explicit_utc_instant
from app.shared.ids import new_id
from app.shared.exceptions import business_error, not_found

Quantity = Annotated[str, StringConstraints(strict=True, pattern=r"^(0|[1-9][0-9]*)\.[0-9]{3}$")]


class Demand(ScenarioDemand):
    service_id: ExactId
    recipe_id: ExactId | None


class Scenario(ForecastScenario):
    demands: list[Demand] = Field(min_length=1, max_length=50)

    @field_validator("starts_at", "ends_at", mode="before")
    @classmethod
    def explicit_instants(cls, value):
        if not isinstance(value,str) or "T" not in value:
            raise ValueError("Explicit aware ISO scenario instants required")
        return value


class Selection(Fact):
    supplier_id: ExactId
    item_ids: Annotated[tuple[ExactId, ...], Field(min_length=1, max_length=50)]
    pending_order_assumption: Literal["ignore_pending_orders", "all_pending_orders_received"]
    scenario: Scenario | None = None

    @model_validator(mode="after")
    def exact_selection(self):
        ids = (self.supplier_id, *self.item_ids)
        if len(set(self.item_ids)) != len(self.item_ids) or any(value != value.strip() or any(ord(c)<32 for c in value) for value in ids):
            raise ValueError("Explicit unique owned item IDs and supplier required")
        if self.scenario is not None:
            for demand in self.scenario.demands:
                if any(value is not None and value != value.strip() for value in (demand.service_id, demand.recipe_id)):
                    raise ValueError("Exact scenario references required")
        return self


class Item(Fact):
    item_id: ExactId
    unit: Literal["ml", "g", "unit"]
    on_hand: Quantity
    threshold: Quantity
    pending_order_quantity: Quantity
    known_demand: Quantity
    complete_demand: Quantity | None
    proposed_quantity: Quantity

    @model_validator(mode="after")
    def coherent_quantities(self):
        values = (self.on_hand, self.threshold, self.pending_order_quantity, self.known_demand, self.complete_demand, self.proposed_quantity)
        if self.unit == "unit" and any(value is not None and not value.endswith(".000") for value in values):
            raise ValueError("Whole stock units cannot be fractional")
        if self.complete_demand is not None and self.complete_demand != self.known_demand:
            raise ValueError("Complete selected demand must equal original known demand")
        return self


class Preview(Fact):
    institute_id: ExactId
    selection: Selection
    captured_at: AwareDatetime
    coverage: Literal["not_applicable", "complete_selected_norms", "partial_selected_norms"]
    items: tuple[Item, ...]
    source_digest: Digest
    state_fingerprint: Digest
    basis: Literal["original_stock_shortfalls_selected_scenario_and_explicit_pending_assumption_not_supplier_quote"] = "original_stock_shortfalls_selected_scenario_and_explicit_pending_assumption_not_supplier_quote"
    effect: Literal["reorder_proposal_only_no_order_contact_payment_receipt_or_stock_write"] = "reorder_proposal_only_no_order_contact_payment_receipt_or_stock_write"

    @model_validator(mode="after")
    def binding(self):
        if set(row.item_id for row in self.items) != set(self.selection.item_ids) or len(self.items) != len(self.selection.item_ids):
            raise ValueError("Projection must cover exactly the selected items")
        if any(row.complete_demand is not None for row in self.items) != (self.coverage == "complete_selected_norms"):
            raise ValueError("Demand completeness must retain original coverage")
        raw = self.model_dump(mode="json", exclude={"captured_at", "state_fingerprint"})
        if fingerprint(raw) != self.state_fingerprint:raise ValueError("Reorder projection digest mismatch")
        return self


def preview(db, institute, candidate):
    try:
        return _preview(db, institute, candidate)
    except ValueError as error:
        raise business_error("Reorder proposal sources require verification") from error


def _preview(db, institute, candidate):
    selection = Selection.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Selection) else candidate)
    stock.lock_institute(db, institute)
    supplier = suppliers.snapshot(suppliers.require_supplier(db, institute, selection.supplier_id))
    for identifier in selection.item_ids:stock.require_item(db, institute, identifier)
    demands, known, complete = outlook.selected_demand(db, institute, selection.scenario)
    rows = outlook.item_rows(db, institute, len(selection.item_ids), 0, known,
        selection.scenario is not None and complete, item_ids=selection.item_ids)
    field = "conditional_shortfall_after_all_orders" if selection.pending_order_assumption == "all_pending_orders_received" else "known_demand_shortfall"
    items = tuple(Item(item_id=row.item_id, unit=row.unit, on_hand=row.on_hand, threshold=row.threshold,
        pending_order_quantity=row.pending_order_quantity, known_demand=row.known_demand,
        complete_demand=row.complete_demand, proposed_quantity=getattr(row, field)) for row in rows)
    coverage = ("complete_selected_norms" if complete else "partial_selected_norms") if selection.scenario else "not_applicable"
    raw = dict(institute_id=institute, selection=selection.model_dump(mode="json"), coverage=coverage,
        items=[row.model_dump(mode="json") for row in items],
        source_digest=fingerprint(dict(supplier=supplier.model_dump(mode="json"),
            demands=[row.model_dump(mode="json") for row in demands], items=[row.model_dump(mode="json") for row in rows])),
        basis=Preview.model_fields["basis"].default, effect=Preview.model_fields["effect"].default)
    return Preview(**raw, captured_at=utcnow(), state_fingerprint=fingerprint(raw))


class Request(Fact):
    selection: Selection
    expected_state_fingerprint: Digest
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def exact_terms(self):
        if any(value != value.strip() or any(ord(c)<32 for c in value) for value in (self.reason, self.idempotency_key)):
            raise ValueError("Exact proposal reason and recovery key required")
        return self


class Original(Request):
    id: ExactId
    institute_id: ExactId
    actor_id: Actor
    created_at: AwareDatetime
    preview: Preview

    @model_validator(mode="after")
    def binding(self):
        if (self.institute_id != self.preview.institute_id or self.selection != self.preview.selection
            or self.expected_state_fingerprint != self.preview.state_fingerprint or self.created_at < self.preview.captured_at):
            raise ValueError("Retained proposal must bind exact owned projection")
        return self


class Receipt(Fact):
    original: Original
    fingerprint: Digest


def verify(row, institute):
    try:
        result = Original.model_validate(row.original)
        if ((result.id, result.institute_id, result.actor_id, result.idempotency_key, result.created_at)
            != (row.id, institute, row.actor_id, row.idempotency_key, explicit_utc_instant(row.created_at))
            or row.institute_id != institute or row.fingerprint != fingerprint(row.original)):
            raise ValueError("Proposal columns or digest mismatch")
        return Envelope(original=row.original, fingerprint=row.fingerprint)
    except (ValueError, TypeError, KeyError) as error:
        raise business_error("Retained reorder original requires verification") from error


def create(db, institute, candidate, actor):
    try:
        request = Request.model_validate(candidate.model_dump(mode="json") if isinstance(candidate, Request) else candidate)
        if not isinstance(actor,str) or not actor or actor != actor.strip() or len(actor)>160 or any(ord(c)<32 for c in actor):
            raise business_error("Signed proposal actor required")
        stock.lock_institute(db, institute)
        old = db.scalar(select(StockReorderOriginal).where(StockReorderOriginal.institute_id==institute,
            StockReorderOriginal.idempotency_key==request.idempotency_key).execution_options(populate_existing=True))
        if old is not None:
            receipt = verify(old, institute)
            original = Original.model_validate(receipt.original)
            if original.actor_id != actor or Request.model_validate(original.model_dump(mode="json", include=set(Request.model_fields))) != request:
                raise business_error("Proposal key retains exact actor and request")
            return receipt
        observed = preview(db, institute, request.selection)
        if observed.state_fingerprint != request.expected_state_fingerprint:
            raise business_error("Proposal sources changed; review a new preview")
        original = Original(**request.model_dump(mode="json"), id=new_id("stock_reorder"), institute_id=institute,
            actor_id=actor, created_at=utcnow(), preview=observed)
        raw = original.model_dump(mode="json")
        row = StockReorderOriginal(id=original.id, institute_id=institute, actor_id=actor,
            idempotency_key=original.idempotency_key, created_at=original.created_at, original=raw, fingerprint=fingerprint(raw))
        db.add(row);db.flush()
        result = verify(row, institute)
        db.commit()
        return result
    except ValueError as error:
        db.rollback();raise business_error("Explicit reorder proposal terms required") from error
    except Exception:
        db.rollback();raise


def require(db, institute, identifier):
    stock.lock_institute(db, institute)
    row = db.scalar(select(StockReorderOriginal).where(StockReorderOriginal.institute_id==institute, StockReorderOriginal.id==identifier).execution_options(populate_existing=True))
    if row is None:raise not_found("Reorder original not found")
    return verify(row, institute)
