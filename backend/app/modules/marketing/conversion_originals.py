"""Owned immutable declared attribution events; historical billing is never recaptured."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Literal
from pydantic import AwareDatetime, model_validator
from sqlalchemy import select, func
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.policies import Reason, Key
from app.modules.marketing import conversions, conversion_sources, dispatch_intents, dispatch_outcomes, campaign_originals, catalogs, provider
from app.modules.marketing.models import ConversionOriginal, ConversionHead
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error, not_found
from app.shared.ids import new_id
from app.shared.time import utcnow, explicit_utc_instant


class Request(Fact):
    action: Literal["linked", "retracted"]
    ticket_id: Identifier
    expected_previous_id: Identifier | None
    selection: conversion_sources.Request | None
    reason: Reason
    idempotency_key: Key

    @model_validator(mode="after")
    def selected_terms(self):
        if (self.action == "linked") != (self.selection is not None):
            raise ValueError("Link requires selected sources; retraction preserves predecessor sources")
        if self.action == "retracted" and self.expected_previous_id is None:
            raise ValueError("Retraction requires a selected linked predecessor")
        if self.selection and (self.selection.ticket_id, self.selection.reason, self.selection.idempotency_key) != (self.ticket_id, self.reason, self.idempotency_key):
            raise ValueError("Selected attribution request terms differ")
        return self


class Original(Fact):
    id: Identifier
    institute_id: Identifier
    request: Request
    actor_id: provider.Exact
    created_at: AwareDatetime
    attribution: conversions.Attribution
    attribution_fingerprint: provider.Fingerprint


def fingerprint(attribution):
    attribution = conversions.Attribution.model_validate(attribution.model_dump())
    def normalize(value):
        if isinstance(value, datetime): return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, dict): return {k: normalize(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)): return [normalize(v) for v in value]
        return value
    return sha256(json.dumps(normalize(attribution.model_dump()), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def row_by_id(db, institute, identifier):
    row = db.scalar(select(ConversionOriginal).where(ConversionOriginal.institute_id == institute, ConversionOriginal.id == identifier)
        .execution_options(populate_existing=True))
    if row is None: raise not_found("Attribution original not found")
    return row


def receipt(db, row):
    try:
        value = Original(id=row.id, institute_id=row.institute_id, request=row.request, actor_id=row.actor_id,
            created_at=explicit_utc_instant(row.created_at), attribution=row.attribution, attribution_fingerprint=row.attribution_fingerprint)
        r, a = value.request, value.attribution
        if (r.ticket_id, r.expected_previous_id, r.action, r.reason, r.idempotency_key) != (row.ticket_id, row.previous_id, row.action, row.reason, row.idempotency_key):
            raise ValueError("Attribution event terms differ")
        if (a.ticket.institute_id, a.ticket.ticket_id, a.intent.id, a.intent.request.campaign_id, a.authorization.revision.id, a.accepted.id) != (
            row.institute_id, row.ticket_id, row.intent_id, row.campaign_id, row.authorization_id, row.accepted_outcome_id):
            raise ValueError("Attribution source columns differ")
        if fingerprint(a) != value.attribution_fingerprint or value.created_at < a.window.captured_at:
            raise ValueError("Attribution fingerprint/event clock differs")
        if value.actor_id != value.actor_id.strip() or any(ord(c) < 32 or ord(c) == 127 for c in value.actor_id):
            raise ValueError("Invalid attribution event actor")
        if r.action == "linked":
            if value.created_at != a.window.captured_at or (value.actor_id, r.reason, r.idempotency_key) != (a.actor_id, a.reason, a.idempotency_key):
                raise ValueError("Linked attribution capture/event differs")
            s = r.selection
            if (s.intent_id, s.expected_fingerprint, s.authorization_id, s.accepted_outcome_id, s.start, s.end) != (
                a.intent.id, a.intent.request_fingerprint, a.authorization.revision.id, a.accepted.id, a.window.start, a.window.end):
                raise ValueError("Linked attribution selection differs")
        if dispatch_intents.require(db, row.institute_id, row.intent_id) != a.intent or campaign_originals.require(db, row.institute_id, row.authorization_id) != a.authorization or dispatch_outcomes.require(db, row.institute_id, row.intent_id, row.accepted_outcome_id) != a.accepted:
            raise ValueError("Retained attribution source original changed")
        return value
    except (ValueError, TypeError):
        raise business_error("Stored attribution original is incoherent") from None


def require(db, institute, identifier):
    lock_institute(db, institute)
    cursor = row_by_id(db, institute, identifier); result = receipt(db, cursor)
    child = result; seen = {child.id}
    while child.request.expected_previous_id is not None:
        if len(seen) >= 1000: raise business_error("Attribution chain exceeds verified read budget")
        prior = receipt(db, row_by_id(db, institute, child.request.expected_previous_id))
        if prior.id in seen or prior.request.ticket_id != child.request.ticket_id or prior.created_at > child.created_at:
            raise business_error("Attribution predecessor chain is incoherent")
        if child.request.action == "retracted" and (prior.request.action != "linked" or child.attribution != prior.attribution):
            raise business_error("Retraction must preserve exact linked predecessor")
        seen.add(prior.id); child = prior
    return result


def original(db, institute, key):
    lock_institute(db, institute)
    row = db.scalar(select(ConversionOriginal.id).where(ConversionOriginal.institute_id == institute, ConversionOriginal.idempotency_key == key))
    return require(db, institute, row) if row else None


def current(db, institute, ticket):
    lock_institute(db, institute)
    pointer = db.scalar(select(ConversionHead).where(ConversionHead.institute_id == institute, ConversionHead.ticket_id == ticket).execution_options(populate_existing=True))
    value = require(db, institute, pointer.original_id) if pointer else None
    if value and value.request.ticket_id != ticket: raise business_error("Attribution current pointer belongs to another ticket")
    return value


def execute(db, institute, payload, actor):
    payload = Request.model_validate(payload.model_dump())
    if not isinstance(actor, str) or not actor or actor != actor.strip() or len(actor) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in actor):
        raise business_error("Signed exact attribution actor required")
    lock_institute(db, institute)
    old = original(db, institute, payload.idempotency_key)
    if old:
        if old.actor_id != actor or old.request != payload: raise business_error("Attribution key retains original actor and full terms")
        return old
    previous = current(db, institute, payload.ticket_id)
    if (previous.id if previous else None) != payload.expected_previous_id:
        raise business_error("Attribution current predecessor changed")
    if previous is None and db.scalar(select(func.count()).select_from(ConversionOriginal).where(ConversionOriginal.institute_id == institute, ConversionOriginal.ticket_id == payload.ticket_id)):
        raise business_error("Attribution history has no current pointer")
    if payload.action == "retracted":
        if previous is None or previous.request.action != "linked": raise business_error("Only a current linked attribution can be retracted")
        attribution, at = previous.attribution, utcnow()
    else:
        attribution = conversion_sources.validate(db, institute, payload.selection, actor).attribution
        at = attribution.window.captured_at
    if previous and at < previous.created_at: raise business_error("Attribution capture precedes retained predecessor")
    a = attribution
    row = ConversionOriginal(id=new_id("marketing_conversion"), institute_id=institute, ticket_id=payload.ticket_id,
        campaign_id=a.intent.request.campaign_id, intent_id=a.intent.id, authorization_id=a.authorization.revision.id, accepted_outcome_id=a.accepted.id,
        previous_id=payload.expected_previous_id, action=payload.action, actor_id=actor, reason=payload.reason, idempotency_key=payload.idempotency_key,
        created_at=at, request=payload.model_dump(mode="json"), attribution=a.model_dump(mode="json"), attribution_fingerprint=fingerprint(a))
    try:
        db.add(row); db.flush()
        pointer = db.get(ConversionHead, (institute, payload.ticket_id))
        if pointer: pointer.original_id = row.id
        else: db.add(ConversionHead(institute_id=institute, ticket_id=payload.ticket_id, original_id=row.id))
        db.flush(); retained = require(db, institute, row.id); db.commit()
        return retained
    except Exception:
        db.rollback(); raise


def audit(db, institute, ticket, offset=0, limit=20):
    catalogs.bounds(db, institute, offset, limit)
    scope = (ConversionOriginal.institute_id == institute, ConversionOriginal.ticket_id == ticket)
    total = db.scalar(select(func.count()).select_from(ConversionOriginal).where(*scope))
    ids = db.scalars(select(ConversionOriginal.id).where(*scope).order_by(ConversionOriginal.created_at, ConversionOriginal.id).offset(offset).limit(limit))
    return catalogs.Page[Original](institute_id=institute, total=total, offset=offset, limit=limit, items=tuple(require(db, institute, identity) for identity in ids))
