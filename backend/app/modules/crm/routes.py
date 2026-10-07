from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.crm import policies
from app.modules.crm import profile
from app.modules.crm import return_sources
from app.modules.crm import lifetime_originals as lifetime
from app.modules.crm import lifecycle_originals as lifecycle, calendar_policies as calendar

from app.modules.crm import event_ledger
from app.modules.crm import event_sources
from app.modules.crm import automation_originals as automation

router = APIRouter(prefix="/crm/institutes/{institute_id}", tags=["crm"])


def manager(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id or user.get("role") != "responsable_institut":
        raise HTTPException(403, "Permission insuffisante")
    return user


@router.post("/customers/{customer_id}/event-captures", response_model=event_ledger.CaptureRead)
def event_capture_create(institute_id: str, customer_id: str, payload: event_ledger.Request, user=Depends(manager), db: Session = Depends(get_db)):
    return event_ledger.execute(db,institute_id,customer_id,payload,user.get("sub"))


@router.get("/customers/{customer_id}/event-captures/original/{key}", response_model=event_ledger.CaptureRead | None)
def event_capture_original(institute_id: str, customer_id: str, key: str, user=Depends(manager), db: Session = Depends(get_db)):
    return event_ledger.original(db,institute_id,customer_id,key)


@router.get("/customers/{customer_id}/event-captures/{identifier}", response_model=event_ledger.CaptureRead)
def event_capture_detail(institute_id: str, customer_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    return event_ledger.require(db,institute_id,customer_id,identifier)


@router.get("/customers/{customer_id}/events", response_model=event_ledger.CurrentPage)
def event_current_page(institute_id: str, customer_id: str, limit: int = Query(20,ge=1,le=50), offset: int = Query(0,ge=0), user=Depends(manager), db: Session = Depends(get_db)):
    return event_ledger.page(db,institute_id,customer_id,limit,offset)


@router.get("/customers/{customer_id}/event-sources", response_model=event_sources.EventSourceRead)
def event_source_read(institute_id: str, customer_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return event_sources.read(db,institute_id,customer_id)


@router.post("/automation-policies", response_model=automation.PolicyRead)
def automation_create(institute_id: str, payload: automation.PolicyCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return automation.create(db,institute_id,payload,user.get("sub"))


@router.get("/automation-policies/current", response_model=automation.PolicyRead | None)
def automation_current(institute_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return automation.current(db,institute_id)


@router.get("/automation-policies/original/{key}", response_model=automation.PolicyRead | None)
def automation_original(institute_id: str, key: str, user=Depends(manager), db: Session = Depends(get_db)):
    return automation.original(db,institute_id,key)


@router.get("/automation-policies/{identifier}", response_model=automation.PolicyRead)
def automation_detail(institute_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    return automation.require(db,institute_id,identifier)


@router.post("/birthday-calendar-policies", response_model=calendar.PolicyRead)
def calendar_create(institute_id: str, payload: calendar.PolicyCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return calendar.create(db,institute_id,payload,user.get("sub"))


@router.get("/birthday-calendar-policies/current", response_model=calendar.PolicyRead | None)
def calendar_current(institute_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return calendar.current(db,institute_id)


@router.get("/birthday-calendar-policies/original/{key}", response_model=calendar.PolicyRead | None)
def calendar_original(institute_id: str, key: str, user=Depends(manager), db: Session = Depends(get_db)):
    return calendar.original(db,institute_id,key)


@router.get("/birthday-calendar-policies/{identifier}", response_model=calendar.PolicyRead)
def calendar_detail(institute_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    return calendar.require(db,institute_id,identifier)


@router.post("/customers/{customer_id}/lifecycle-declarations", response_model=lifecycle.Original)
def lifecycle_create(institute_id: str, customer_id: str, payload: lifecycle.Declaration, user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.create(db,institute_id,customer_id,payload,user.get("sub"))


@router.get("/customers/{customer_id}/lifecycle-declarations/current", response_model=lifecycle.Original | None)
def lifecycle_current(institute_id: str, customer_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.current(db,institute_id,customer_id)


@router.get("/customers/{customer_id}/lifecycle-declarations/original/{key}", response_model=lifecycle.Original | None)
def lifecycle_original(institute_id: str, customer_id: str, key: str, user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.original(db,institute_id,customer_id,key)


@router.get("/customers/{customer_id}/lifecycle-declarations/{identifier}", response_model=lifecycle.Original)
def lifecycle_detail(institute_id: str, customer_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    lifecycle.owned(db,institute_id,customer_id)
    return lifecycle.require(db,institute_id,customer_id,identifier)


@router.get("/customers/{customer_id}/lifecycle", response_model=lifecycle.LifecycleRead)
def lifecycle_read(institute_id: str, customer_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return lifecycle.read(db,institute_id,customer_id)


@router.post("/customers/{customer_id}/lifetime-assumptions", response_model=lifetime.Original)
def lifetime_create(institute_id: str, customer_id: str, payload: lifetime.Declaration, user=Depends(manager), db: Session = Depends(get_db)):
    return lifetime.create(db,institute_id,customer_id,payload,user.get("sub"))


@router.get("/customers/{customer_id}/lifetime-assumptions/current", response_model=lifetime.Original | None)
def lifetime_current(institute_id: str, customer_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return lifetime.current(db,institute_id,customer_id)


@router.get("/customers/{customer_id}/lifetime-assumptions/original/{key}", response_model=lifetime.Original | None)
def lifetime_original(institute_id: str, customer_id: str, key: str, user=Depends(manager), db: Session = Depends(get_db)):
    return lifetime.original(db,institute_id,customer_id,key)


@router.get("/customers/{customer_id}/lifetime-assumptions/{identifier}", response_model=lifetime.Original)
def lifetime_detail(institute_id: str, customer_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    lifetime.owned(db,institute_id,customer_id)
    return lifetime.require(db,institute_id,customer_id,identifier)


@router.get("/customers/{customer_id}/lifetime-scenario", response_model=lifetime.ScenarioRead)
def lifetime_scenario(institute_id: str, customer_id: str, start: str = Query(min_length=1,max_length=64), user=Depends(manager), db: Session = Depends(get_db)):
    return lifetime.read(db,institute_id,customer_id,start)


@router.get("/customers/{customer_id}/segment", response_model=profile.SegmentProfile)
def segment(institute_id: str, customer_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return profile.read(db, institute_id, customer_id)


@router.get("/customers/{customer_id}/return-cycle", response_model=return_sources.ReturnRead)
def return_cycle(institute_id: str, customer_id: str,
                 start: str = Query(min_length=1, max_length=64), end: str = Query(min_length=1, max_length=64),
                 limit: int = Query(default=20, ge=1, le=50), offset: int = Query(default=0, ge=0),
                 user=Depends(manager), db: Session = Depends(get_db)):
    return return_sources.read(db, institute_id, customer_id, start, end, limit, offset)


@router.post("/segment-policies", response_model=policies.PolicyRead)
def create(institute_id: str, payload: policies.PolicyCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.create(db, institute_id, payload, user.get("sub"))


@router.get("/segment-policies/current", response_model=policies.PolicyRead | None)
def current(institute_id: str, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.current(db, institute_id)


@router.get("/segment-policies/original/{key}", response_model=policies.PolicyRead | None)
def original(institute_id: str, key: str, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.original(db, institute_id, key)


@router.get("/segment-policies/{identifier}", response_model=policies.PolicyRead)
def detail(institute_id: str, identifier: str, user=Depends(manager), db: Session = Depends(get_db)):
    return policies.require(db, institute_id, identifier)
