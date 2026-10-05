from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.memberships import service
from app.modules.memberships.models import CustomerMembership, MembershipPlan, MembershipRenewal
from app.modules.memberships.schemas import MembershipIssue, MembershipRead, MembershipRenew, PlanCreate, PlanRead, RenewalRead

router = APIRouter(prefix="/memberships/institutes/{institute_id}", tags=["memberships"])


def scoped_operator(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id:
        raise HTTPException(403, "Institut non autorise")
    return user


def manager(user=Depends(scoped_operator)):
    if user["role"] != "responsable_institut":
        raise HTTPException(403, "Configuration, attribution et renouvellement reserves a la responsable")
    actor = user.get("sub")
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Identite de la responsable requise pour l'historique")
    return user


@router.get("/plans", response_model=list[PlanRead])
def plans(institute_id: str, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    return db.scalars(select(MembershipPlan).where(MembershipPlan.institute_id == institute_id).order_by(MembershipPlan.name, MembershipPlan.id)).all()


@router.post("/plans", response_model=PlanRead)
def create_plan(institute_id: str, payload: PlanCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return service.create_plan(db, institute_id, payload, user.get("sub"))


@router.get("", response_model=list[MembershipRead])
def memberships(institute_id: str, customer_id: str, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    return [service.membership_view(row) for row in db.scalars(select(CustomerMembership).where(
        CustomerMembership.institute_id == institute_id, CustomerMembership.customer_id == customer_id,
    ).order_by(CustomerMembership.issued_at, CustomerMembership.id))]


@router.post("", response_model=MembershipRead)
def issue(institute_id: str, payload: MembershipIssue, user=Depends(manager), db: Session = Depends(get_db)):
    return service.membership_view(service.issue_membership(db, institute_id, payload, user.get("sub")))


@router.post("/{membership_id}/renew", response_model=RenewalRead)
def renew(institute_id: str, membership_id: str, payload: MembershipRenew, user=Depends(manager), db: Session = Depends(get_db)):
    return service.renew_membership(db, institute_id, membership_id, payload, user.get("sub"))


@router.get("/{membership_id}/history", response_model=list[RenewalRead])
def history(institute_id: str, membership_id: str, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    service.scoped_membership(db, institute_id, membership_id)
    return db.scalars(select(MembershipRenewal).where(MembershipRenewal.institute_id == institute_id,
        MembershipRenewal.membership_id == membership_id).order_by(MembershipRenewal.occurred_at, MembershipRenewal.id)).all()
