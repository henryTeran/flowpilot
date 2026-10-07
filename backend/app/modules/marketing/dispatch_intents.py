"""Owned durable preparation, with protected historical replay and no transport I/O."""
import json
from pydantic import AwareDatetime
from sqlalchemy import select
from app.core.config import settings
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.policies import Reason, Key
from app.modules.crm.segments import RegisteredCustomerFact
from app.modules.marketing import campaign_originals, contact_originals, contacts, provider
from app.modules.marketing.models import DispatchIntent
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import explicit_utc_instant, utcnow

class Request(Fact):
    campaign_id: Identifier
    expected_revision_id: Identifier
    customer_id: Identifier
    expected_contact_id: Identifier
    account_id: provider.Exact
    reason: Reason
    idempotency_key: Key

class Original(Fact):
    id: Identifier
    request: Request
    submission: provider.Submission
    created_at: AwareDatetime
    request_fingerprint: provider.Fingerprint

def configured(institute, channel, identifier):
    try:
        raw = json.loads(settings.MARKETING_ACCOUNTS_JSON)
        if not isinstance(raw, list): raise ValueError("Expected configured account list")
        accounts = [provider.Account.model_validate(a) for a in raw]
        scopes = [(a.institute_id, a.channel, a.account_id) for a in accounts]
        if len(scopes) != len(set(scopes)): raise ValueError("Ambiguous configured accounts")
        selected = [a for a in accounts if (a.institute_id, a.channel, a.account_id) == (institute, channel, identifier)]
        if len(selected) != 1: raise ValueError("No configured channel account")
        return selected[0]
    except (ValueError, TypeError) as error:
        raise business_error("Marketing account is absent or configuration is invalid") from error

def receipt(db, row):
    try:
        s = provider.Submission.model_validate(row.submission)
        e = s.eligibility
        r = Request(campaign_id=row.campaign_id, expected_revision_id=row.approval_id, customer_id=row.customer_id,
            expected_contact_id=row.contact_id, account_id=s.account.account_id, reason=row.reason, idempotency_key=row.idempotency_key)
        at = explicit_utc_instant(row.created_at)
        if (s.account.institute_id, e.campaign.campaign_id, e.campaign.id, e.customer.customer_id, e.original.id, s.actor_id,
                s.idempotency_key, e.captured_at, provider.fingerprint(s)) != (row.institute_id, row.campaign_id, row.approval_id,
                row.customer_id, row.contact_id, row.actor_id, row.idempotency_key, at, row.request_fingerprint): raise ValueError("Stored terms differ")
        if r.reason != row.reason or r.idempotency_key != row.idempotency_key: raise ValueError("Stored terms were normalized")
        approval = campaign_originals.require(db, row.institute_id, row.approval_id)
        contact = contact_originals.require(db, row.institute_id, row.customer_id, row.contact_id)
        if approval.revision != e.campaign or contact != e.original: raise ValueError("Historical source differs")
        return Original(id=row.id, request=r, submission=s, created_at=at, request_fingerprint=row.request_fingerprint)
    except ValueError as error:
        raise business_error("Stored dispatch intent or historical source is incoherent") from error

def original(db, institute, key):
    lock_institute(db, institute)
    row = db.scalar(select(DispatchIntent).where(DispatchIntent.institute_id == institute, DispatchIntent.idempotency_key == key).execution_options(populate_existing=True))
    return receipt(db, row) if row else None

def require(db, institute, identifier):
    lock_institute(db, institute)
    row = db.scalar(select(DispatchIntent).where(DispatchIntent.institute_id == institute, DispatchIntent.id == identifier).execution_options(populate_existing=True))
    if row is None: raise not_found("Dispatch intent not found")
    return receipt(db, row)

def prepare(db, institute, payload, actor):
    payload = Request.model_validate(payload.model_dump())
    lock_institute(db, institute)
    old = original(db, institute, payload.idempotency_key)
    if old is not None:
        if old.request != payload or old.submission.actor_id != actor: raise business_error("Dispatch key retains original terms and actor")
        return old
    campaign = campaign_originals.current(db, institute, payload.campaign_id)
    if campaign is None or campaign.revision.id != payload.expected_revision_id: raise business_error("Campaign revision changed")
    customer = contact_originals.owned(db, institute, payload.customer_id)
    contact = contact_originals.current(db, institute, payload.customer_id)
    if contact is None or contact.id != payload.expected_contact_id: raise business_error("Marketing contact changed")
    prior = db.scalar(select(DispatchIntent.id).where(DispatchIntent.institute_id == institute, DispatchIntent.approval_id == payload.expected_revision_id,
        DispatchIntent.customer_id == payload.customer_id))
    if prior is not None: raise business_error("Approved recipient already has a dispatch intent; recover its original")
    account = configured(institute, campaign.revision.content.channel, payload.account_id)
    try:
        at = utcnow()
        registered = RegisteredCustomerFact(institute_id=institute, customer_id=payload.customer_id, created_at=explicit_utc_instant(customer.created_at))
        eligible = contacts.evaluate(registered, campaign.revision, contact, at)
        submission = provider.Submission(account=account, eligibility=eligible, actor_id=actor, idempotency_key=payload.idempotency_key)
    except ValueError as error:
        raise business_error("Approved recipient sources do not permit dispatch preparation") from error
    row = DispatchIntent(id=new_id("marketing_dispatch"), institute_id=institute, campaign_id=payload.campaign_id, approval_id=payload.expected_revision_id,
        customer_id=payload.customer_id, contact_id=payload.expected_contact_id, actor_id=actor, reason=payload.reason, idempotency_key=payload.idempotency_key,
        created_at=at, request_fingerprint=provider.fingerprint(submission), submission=submission.model_dump(mode="json"))
    try:
        db.add(row); db.flush(); retained = receipt(db, row); db.commit(); return retained
    except Exception:
        db.rollback(); raise
