from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.permissions import require_ticket_manager
from app.database.session import get_db
from app.modules.customers.schemas import CustomerCreate, CustomerRead
from app.modules.customers.service import create_customer, search_customers
from app.modules.customers.repository import require_customer
from app.modules.crm.billing import read as read_billing
from app.modules.crm.metrics import RecordedBilling

router = APIRouter(prefix="/customers/institutes/{institute_id}", tags=["customers"])


def operator(institute_id: str, user=Depends(require_ticket_manager)):
    if user.get("institute_id") != institute_id:
        raise HTTPException(403, "Institut non autorise")
    return user


def billing_operator(user=Depends(operator)):
    if user.get("role") != "responsable_institut":
        raise HTTPException(403, "Permission insuffisante")
    return user


@router.get("/{customer_id}/billing", response_model=RecordedBilling)
def billing(institute_id: str, customer_id: str,
            start: str = Query(min_length=1, max_length=64),
            end: str = Query(min_length=1, max_length=64),
            user=Depends(billing_operator), db: Session = Depends(get_db)):
    return read_billing(db, institute_id, customer_id, start, end)


@router.get("", response_model=list[CustomerRead])
def search(institute_id: str, q: str = Query(default="", max_length=160), limit: int = Query(default=20, ge=1, le=50),
           user=Depends(operator), db: Session = Depends(get_db)):
    return search_customers(db, institute_id, q, limit)


@router.post("", response_model=CustomerRead)
def create(institute_id: str, payload: CustomerCreate, user=Depends(operator), db: Session = Depends(get_db)):
    return create_customer(db, institute_id, payload, user.get("sub"))


@router.get("/{customer_id}", response_model=CustomerRead)
def detail(institute_id: str, customer_id: str, user=Depends(operator), db: Session = Depends(get_db)):
    return require_customer(db, institute_id, customer_id)
