from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.session import get_db
from app.modules.auth.models import User
from app.modules.auth.repository import get_user_by_email
from app.modules.employees.models import Employee
from app.modules.institutes.models import Company, Country, Institute, Region
from app.modules.services.models import Service, ServiceCategory
from app.shared.responses import ok

router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/init-demo-data")
def init_demo_data(db: Session = Depends(get_db)):
    """
    Seed minimal pour tester le MVP localement.

    Important :
    - On force les db.flush() après les entités parentes.
    - On évite save_user() ici, car cette fonction fait un commit trop tôt.
    - On fait un seul db.commit() final.
    """

    company = db.get(Company, "demo-company-bodyminute")
    if not company:
        company = Company(
            id="demo-company-bodyminute",
            name="BodyMinute Demo",
            status="active",
        )
        db.add(company)
        db.flush()

    country = db.get(Country, "demo-country-ch")
    if not country:
        country = Country(
            id="demo-country-ch",
            company_id=company.id,
            code="CH",
            name="Suisse",
        )
        db.add(country)
        db.flush()

    region = db.get(Region, "demo-region-geneve")
    if not region:
        region = Region(
            id="demo-region-geneve",
            country_id=country.id,
            name="Genève",
        )
        db.add(region)
        db.flush()

    institute = db.get(Institute, "demo-institute-geneve")
    if not institute:
        institute = Institute(
            id="demo-institute-geneve",
            region_id=region.id,
            name="BodyMinute Genève Demo",
            city="Genève",
            address="Rue de démonstration 1",
            timezone="Europe/Zurich",
            status="active",
        )
        db.add(institute)
        db.flush()

    categories = [
        ("cat-epilation", "Épilation", "EPILATION"),
        ("cat-manucure", "Manucure / Pédicure", "MANUCURE"),
        ("cat-soins", "Soins visage / corps", "SOINS"),
        ("cat-vente", "Vente", "VENTE"),
    ]

    for category_id, name, code in categories:
        if not db.get(ServiceCategory, category_id):
            db.add(
                ServiceCategory(
                    id=category_id,
                    name=name,
                    code=code,
                )
            )

    db.flush()

    services = [
        ("svc-aisselles", "cat-epilation", "Aisselles", 10, 10, 9.90, 15.00),
        ("svc-sourcils", "cat-epilation", "Sourcils", 10, 10, 9.90, 15.00),
        ("svc-jambes-completes", "cat-epilation", "Jambes complètes", 20, 20, 24.90, 35.00),
        ("svc-semi-main", "cat-manucure", "Semi permanent mains", 30, 30, 29.90, 39.00),
        ("svc-beaute-pieds", "cat-manucure", "Beauté des pieds", 40, 40, 39.90, 49.00),
        ("svc-soin-profond", "cat-soins", "Soin profond", 50, 50, 59.90, 79.00),
    ]

    for service_id, category_id, name, duration_min, duration_max, price_member, price_passage in services:
        if not db.get(Service, service_id):
            db.add(
                Service(
                    id=service_id,
                    category_id=category_id,
                    name=name,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    price_member=price_member,
                    price_passage=price_passage,
                    requires_machine=False,
                    requires_appointment=False,
                    status="active",
                )
            )

    db.flush()

    employees = [
        ("emp-angela", "Angela", "A01"),
        ("emp-camille", "Camille", "C01"),
        ("emp-clara", "Clara", "C02"),
        ("emp-assya", "Assya", "A02"),
    ]

    for employee_id, first_name, code in employees:
        if not db.get(Employee, employee_id):
            db.add(
                Employee(
                    id=employee_id,
                    institute_id=institute.id,
                    user_id=None,
                    first_name=first_name,
                    code=code,
                    skills=["EPILATION", "MANUCURE", "SOINS"],
                    status="available",
                )
            )

    if not get_user_by_email(db, "accueil@bodyminute.demo"):
        db.add(
            User(
                id="user-accueil-demo",
                email="accueil@bodyminute.demo",
                password_hash=hash_password("demo1234"),
                role="accueil",
                status="active",
                institute_id=institute.id,
            )
        )

    db.commit()

    return ok(
        {
            "institute_id": institute.id,
            "login": "accueil@bodyminute.demo",
            "password": "demo1234",
        },
        "Données de démonstration initialisées",
    )