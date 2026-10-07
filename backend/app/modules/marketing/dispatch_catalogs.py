"""Owned bounded dispatch selection; metadata and historical intents never execute I/O."""
from sqlalchemy import select, func
from app.modules.marketing import catalogs, dispatch_intents, campaign_originals, provider
from app.modules.marketing.models import DispatchIntent
from app.shared.exceptions import business_error, not_found
from app.modules.customers.repository import require_customer


def accounts(db, institute, channel, offset=0, limit=20):
    catalogs.bounds(db, institute, offset, limit)
    if channel not in ("email", "sms", "push"): raise business_error("Explicit marketing channel required")
    selected = sorted((account for account in dispatch_intents.account_catalog()
        if account.institute_id == institute and account.channel == channel), key=lambda account: account.account_id)
    return catalogs.Page[provider.Account](institute_id=institute, total=len(selected), offset=offset, limit=limit,
        items=tuple(selected[offset:offset + limit]))


def intents(db, institute, campaign, offset=0, limit=20):
    catalogs.bounds(db, institute, offset, limit)
    if campaign_originals.current(db, institute, campaign) is None: raise not_found("Campaign not found")
    scope = (DispatchIntent.institute_id == institute, DispatchIntent.campaign_id == campaign)
    total = db.scalar(select(func.count()).select_from(DispatchIntent).where(*scope))
    rows = db.scalars(select(DispatchIntent).where(*scope).order_by(DispatchIntent.created_at, DispatchIntent.id)
        .offset(offset).limit(limit).execution_options(populate_existing=True))
    return catalogs.Page[dispatch_intents.Original](institute_id=institute, total=total, offset=offset, limit=limit,
        items=tuple(dispatch_intents.receipt(db, row) for row in rows))


def recipient_intent(db, institute, campaign, approval, customer):
    """Exact unique historical selection; absence never grants dispatch authority."""
    catalogs.bounds(db, institute, 0, 1)
    if campaign_originals.current(db, institute, campaign) is None: raise not_found("Campaign not found")
    original = campaign_originals.require(db, institute, approval)
    if original.revision.campaign_id != campaign or original.revision.state != "APPROVE":
        raise business_error("Owned approved campaign revision required")
    require_customer(db, institute, customer)
    row = db.scalar(select(DispatchIntent).where(DispatchIntent.institute_id == institute,
        DispatchIntent.campaign_id == campaign, DispatchIntent.approval_id == approval,
        DispatchIntent.customer_id == customer).execution_options(populate_existing=True))
    return None if row is None else dispatch_intents.receipt(db, row)
