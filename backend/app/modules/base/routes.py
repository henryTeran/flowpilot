"""Signed BASE discovery, selection context and registered read/suggest calls."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Literal
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base import read_capabilities as base
from app.modules.base import intents
from app.modules.base import plans
from app.modules.base import sensitive_capabilities as sensitive
from app.modules.waitlist.originals import Envelope as RetainedEnvelope
from app.modules.crm.metrics import Fact
from app.modules.waitlist.originals import fingerprint

router = APIRouter(prefix="/base/institutes/{institute_id}", tags=["base"])


def principal(institute_id: str, user=Depends(require_ticket_manager)):
    return base.signed_principal(user, institute_id)


class Discovery(Fact):
    principal: base.Principal
    capabilities: tuple[base.Capability, ...]
    basis: Literal["registered_capabilities_allowed_in_exact_signed_scope"] = "registered_capabilities_allowed_in_exact_signed_scope"


class Envelope(Fact):
    evidence: base.Evidence
    fingerprint: base.Digest
    integrity: Literal["full_response_sha256_not_retention_or_signature"] = "full_response_sha256_not_retention_or_signature"


@router.get("/capabilities", response_model=Discovery)
def discovery(institute_id: str, user: base.Principal = Depends(principal)):
    return Discovery(principal=user, capabilities=base.capabilities(user, institute_id))


@router.get("/sensitive-capabilities", response_model=tuple[sensitive.Capability, ...])
def sensitive_discovery(institute_id: str, user: base.Principal = Depends(principal)):
    return sensitive.capabilities(user, institute_id)


@router.post("/sensitive-previews/appointment-cancel", response_model=sensitive.Preview)
def cancellation_preview(institute_id: str, body: sensitive.Selection, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return sensitive.preview(db, user, institute_id, body)


@router.post("/contexts/resolve", response_model=base.Context)
def context(institute_id: str, body: base.Invocation, user: base.Principal = Depends(principal)):
    value, _ = base.resolve(user, institute_id, body)
    return value


@router.post("/intents/resolve", response_model=intents.Resolution)
def intent(institute_id: str, body: intents.Request, user: base.Principal = Depends(principal)):
    return intents.resolve(user, institute_id, body)


@router.post("/plans", response_model=RetainedEnvelope)
def prepare(institute_id: str, body: plans.Request, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.create(db, user, institute_id, body)


@router.get("/plan-by-key", response_model=RetainedEnvelope | None)
def recover(institute_id: str, key: str = Query(min_length=1, max_length=120), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.by_key(db, user, institute_id, key)


@router.get("/plans", response_model=plans.Audit)
def history(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.audit(db, user, institute_id, offset, limit)


@router.get("/plans/{identifier}", response_model=RetainedEnvelope)
def plan(institute_id: str, identifier: str, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.require(db, user, institute_id, identifier)


@router.post("/reads", response_model=Envelope)
def read(institute_id: str, body: base.Invocation, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    evidence = base.invoke(db, user, institute_id, body)
    return Envelope(evidence=evidence, fingerprint=fingerprint(evidence.model_dump(mode="json")))
