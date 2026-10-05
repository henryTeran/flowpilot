from sqlalchemy import select
from app.modules.customers.models import Customer
from app.shared.exceptions import not_found


def require_customer(db, institute_id, customer_id):
    row = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.institute_id == institute_id))
    if row is None:
        raise not_found("Cliente introuvable")
    return row


def validate_customer_reference(db, institute_id, customer_id):
    """Validate registered identities; preserve historical opaque ticket references."""
    if customer_id and (customer_id.startswith("customer_") or db.get(Customer, customer_id) is not None):
        require_customer(db, institute_id, customer_id)
