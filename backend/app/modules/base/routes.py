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
from app.modules.base import sensitive_originals as operations
from app.modules.base import approvals
from app.modules.base import executions
from app.modules.base import audit
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
@audit.traced("discovery")
def discovery(institute_id: str, user: base.Principal = Depends(principal)):
    return Discovery(principal=user, capabilities=base.capabilities(user, institute_id))


@router.get("/sensitive-capabilities", response_model=tuple[sensitive.Capability, ...])
@audit.traced("sensitive_discovery")
def sensitive_discovery(institute_id: str, user: base.Principal = Depends(principal)):
    return sensitive.capabilities(user, institute_id)


@router.post("/sensitive-previews/appointment-cancel", response_model=sensitive.Preview)
@audit.traced("cancellation_preview")
def cancellation_preview(institute_id: str, body: sensitive.Selection, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return sensitive.preview(db, user, institute_id, body)


@router.post("/sensitive-operations", response_model=RetainedEnvelope)
@audit.traced("prepare_operation")
def prepare_operation(institute_id: str, body: operations.Request, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return operations.create(db, user, institute_id, body)


@router.get("/sensitive-operation-by-key", response_model=RetainedEnvelope | None)
@audit.traced("recover_operation")
def recover_operation(institute_id: str, key: str = Query(min_length=1, max_length=120), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return operations.by_key(db, user, institute_id, key)


@router.get("/sensitive-operations", response_model=operations.Audit)
@audit.traced("operation_history")
def operation_history(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return operations.audit(db, user, institute_id, offset, limit)


@router.get("/sensitive-operations/{identifier}", response_model=RetainedEnvelope)
@audit.traced("operation_detail")
def operation_detail(institute_id: str, identifier: str, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return operations.require(db, user, institute_id, identifier)


@router.post("/approvals", response_model=RetainedEnvelope)
@audit.traced("decision")
def decision(institute_id: str, body: approvals.Request, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return approvals.decide(db, user, institute_id, body)


@router.get("/approval-by-key", response_model=RetainedEnvelope | None)
@audit.traced("recover_decision")
def recover_decision(institute_id: str, key: str = Query(min_length=1, max_length=120), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return approvals.by_key(db, user, institute_id, key)


@router.get("/sensitive-operations/{identifier}/approval-state", response_model=approvals.State)
@audit.traced("approval_state")
def approval_state(institute_id: str, identifier: str, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return approvals.state(db, user, institute_id, identifier)


@router.get("/execution-capabilities", response_model=tuple[executions.Capability, ...])
@audit.traced("execution_capabilities")
def execution_capabilities(institute_id: str, user: base.Principal = Depends(principal)):
    plans.guard(user, institute_id)
    return tuple(executions.REGISTRY.values())


@router.post("/executions", response_model=RetainedEnvelope)
@audit.traced("execute")
def execute(institute_id: str, body: executions.Request, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return executions.execute(db, user, institute_id, body)


@router.get("/execution-by-key", response_model=RetainedEnvelope | None)
@audit.traced("recover_execution")
def recover_execution(institute_id: str, key: str = Query(min_length=1, max_length=120), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return executions.by_key(db, user, institute_id, key)


@router.get("/sensitive-operations/{identifier}/execution", response_model=RetainedEnvelope | None)
@audit.traced("execution_for_operation")
def execution_for_operation(institute_id: str, identifier: str, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return executions.for_operation(db, user, institute_id, identifier)


@router.post("/contexts/resolve", response_model=base.Context)
@audit.traced("context")
def context(institute_id: str, body: base.Invocation, user: base.Principal = Depends(principal)):
    value, _ = base.resolve(user, institute_id, body)
    return value


@router.post("/intents/resolve", response_model=intents.Resolution)
@audit.traced("intent")
def intent(institute_id: str, body: intents.Request, user: base.Principal = Depends(principal)):
    return intents.resolve(user, institute_id, body, interpreter=intents.UpstreamInterpreter())


@router.post("/plans", response_model=RetainedEnvelope)
@audit.traced("prepare")
def prepare(institute_id: str, body: plans.Request, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.create(db, user, institute_id, body)


@router.get("/plan-by-key", response_model=RetainedEnvelope | None)
@audit.traced("recover")
def recover(institute_id: str, key: str = Query(min_length=1, max_length=120), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.by_key(db, user, institute_id, key)


@router.get("/plans", response_model=plans.Audit)
@audit.traced("history")
def history(institute_id: str, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.audit(db, user, institute_id, offset, limit)


@router.get("/plans/{identifier}", response_model=RetainedEnvelope)
@audit.traced("plan")
def plan(institute_id: str, identifier: str, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    return plans.require(db, user, institute_id, identifier)


@router.post("/reads", response_model=Envelope)
@audit.traced("read")
def read(institute_id: str, body: base.Invocation, user: base.Principal = Depends(principal), db: Session = Depends(get_db)):
    evidence = base.invoke(db, user, institute_id, body)
    return Envelope(evidence=evidence, fingerprint=fingerprint(evidence.model_dump(mode="json")))
