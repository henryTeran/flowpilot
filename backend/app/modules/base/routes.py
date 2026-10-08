"""Signed BASE discovery, selection context and registered read/suggest calls."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Literal
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.base import read_capabilities as base
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


@router.post("/contexts/resolve", response_model=base.Context)
def context(institute_id: str, body: base.Invocation, user: base.Principal = Depends(principal)):
    value, _ = base.resolve(user, institute_id, body)
    return value


@router.post("/reads", response_model=Envelope)
def read(institute_id: str, body: base.Invocation, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    evidence = base.invoke(db, user, institute_id, body)
    return Envelope(evidence=evidence, fingerprint=fingerprint(evidence.model_dump(mode="json")))
