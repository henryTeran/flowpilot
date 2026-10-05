from hashlib import sha256
import json
import re
import unicodedata
from sqlalchemy import or_, select
from app.modules.customers.models import Customer
from app.modules.tickets.repository import lock_institute
from app.shared.exceptions import business_error
from app.shared.ids import new_id
from app.shared.time import utcnow


def normalized_name(value):
    return " ".join("".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                            if not unicodedata.combining(char)).split())


def create_customer(db, institute_id, payload, actor):
    lock_institute(db, institute_id)
    name = " ".join(unicodedata.normalize("NFC", payload.display_name).split())
    if not 2 <= len(name) <= 160:
        raise business_error("Le nom de la cliente doit contenir entre 2 et 160 caracteres")
    phone = payload.phone.strip() if payload.phone else None
    fingerprint = sha256(json.dumps({"display_name": name, "phone": phone}, sort_keys=True,
                                    ensure_ascii=False).encode()).hexdigest()
    existing = db.scalar(select(Customer).where(Customer.institute_id == institute_id,
                                               Customer.idempotency_key == payload.idempotency_key))
    if existing:
        if existing.creation_fingerprint != fingerprint:
            raise business_error("Cette cle de rejeu appartient a une autre cliente")
        return existing
    customer = Customer(id=new_id("customer"), institute_id=institute_id, display_name=name,
        phone=phone, search_name=normalized_name(name), phone_digits=re.sub(r"[^0-9]", "", phone or ""),
        idempotency_key=payload.idempotency_key, creation_fingerprint=fingerprint,
        created_at=utcnow(), created_by=actor)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def search_customers(db, institute_id, query, limit):
    name = normalized_name(query)
    if len(name) < 2:
        return []
    criteria = [Customer.search_name.contains(name, autoescape=True)]
    digits = re.sub(r"[^0-9]", "", query)
    if len(digits) >= 3:
        criteria.append(Customer.phone_digits.contains(digits, autoescape=True))
    return db.scalars(select(Customer).where(Customer.institute_id == institute_id, or_(*criteria))
        .order_by(Customer.search_name, Customer.id).limit(limit)).all()
