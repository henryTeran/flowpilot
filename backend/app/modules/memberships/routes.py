from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.memberships import service
from app.modules.memberships.models import CustomerMembership, MembershipPlan, MembershipRenewal
from app.modules.memberships.schemas import MembershipIssue, MembershipRead, MembershipRenew, PlanCreate, PlanRead, RenewalRead
from app.modules.memberships.schemas import BenefitApply, BenefitRead, BenefitReverse
from app.modules.memberships.models import MembershipBenefit
from app.modules.memberships.benefits import apply_benefit, reverse_benefit

router = APIRouter(prefix="/memberships/institutes/{institute_id}", tags=["memberships"])


def scoped_operator(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id:
        raise HTTPException(403, "Institut non autorise")
    return user


def authenticated_operator(user=Depends(scoped_operator)):
    actor = user.get("sub")
    if not isinstance(actor, str) or not actor.strip() or len(actor) > 160:
        raise HTTPException(403, "Identite de l'operatrice requise pour l'historique")
    return user


def manager(user=Depends(authenticated_operator)):
    if user["role"] != "responsable_institut":
        raise HTTPException(403, "Configuration, attribution et renouvellement reserves a la responsable")
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


@router.post("/{membership_id}/benefits", response_model=BenefitRead)
def apply(institute_id: str, membership_id: str, payload: BenefitApply,
          user=Depends(authenticated_operator), db: Session = Depends(get_db)):
    return apply_benefit(db, institute_id, membership_id, payload, user.get("sub"))


@router.get("/{membership_id}/benefits", response_model=list[BenefitRead])
def benefits(institute_id: str, membership_id: str, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    service.scoped_membership(db, institute_id, membership_id)
    return db.scalars(select(MembershipBenefit).where(MembershipBenefit.institute_id == institute_id,
        MembershipBenefit.membership_id == membership_id).order_by(MembershipBenefit.occurred_at, MembershipBenefit.id)).all()


@router.post("/benefits/{benefit_id}/reverse", response_model=BenefitRead)
def reverse(institute_id: str, benefit_id: str, payload: BenefitReverse,
            user=Depends(manager), db: Session = Depends(get_db)):
    return reverse_benefit(db, institute_id, benefit_id, payload.reason, user.get("sub"))
