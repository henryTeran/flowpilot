from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.commerce import service
from app.modules.commerce.models import CustomerPackage, PackagePlan, PackageRedemption
from app.modules.commerce.schemas import PackageConsume, PackageIssue, PackagePlanCreate, PackagePlanRead, PackageRead, RedemptionRead

router = APIRouter(prefix="/commerce/institutes/{institute_id}", tags=["commerce"])


def scoped_operator(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id:
        raise HTTPException(403, "Institut non autorise")
    return user


def manager(user=Depends(scoped_operator)):
    if user["role"] != "responsable_institut":
        raise HTTPException(403, "Attribution et configuration reservees a la responsable")
    return user


@router.get("/package-plans", response_model=list[PackagePlanRead])
def plans(institute_id: str, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    return db.scalars(select(PackagePlan).where(PackagePlan.institute_id == institute_id).order_by(PackagePlan.name, PackagePlan.id)).all()


@router.post("/package-plans", response_model=PackagePlanRead)
def create_plan(institute_id: str, payload: PackagePlanCreate, user=Depends(manager), db: Session = Depends(get_db)):
    return service.create_plan(db, institute_id, payload)


@router.post("/packages", response_model=PackageRead)
def issue(institute_id: str, payload: PackageIssue, user=Depends(manager), db: Session = Depends(get_db)):
    return service.package_view(service.issue_package(db, institute_id, payload, user.get("sub")))


@router.get("/packages", response_model=list[PackageRead])
def packages(institute_id: str, customer_id: str, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    return [service.package_view(item) for item in db.scalars(select(CustomerPackage).where(
        CustomerPackage.institute_id == institute_id, CustomerPackage.customer_id == customer_id).order_by(CustomerPackage.issued_at, CustomerPackage.id))]


@router.post("/packages/{package_id}/consume", response_model=RedemptionRead)
def consume(institute_id: str, package_id: str, payload: PackageConsume, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    return service.consume_package(db, institute_id, package_id, payload, user.get("sub"))


@router.get("/packages/{package_id}/history", response_model=list[RedemptionRead])
def history(institute_id: str, package_id: str, user=Depends(scoped_operator), db: Session = Depends(get_db)):
    service.scoped_package(db, institute_id, package_id)
    return db.scalars(select(PackageRedemption).where(PackageRedemption.package_id == package_id,
        PackageRedemption.institute_id == institute_id).order_by(PackageRedemption.occurred_at, PackageRedemption.id)).all()
