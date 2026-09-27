from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.database.session import get_db
from app.modules.appointments.models import Appointment
from app.modules.auth.models import User
from app.modules.auth.repository import get_user_by_email
from app.modules.employees.models import Employee
from app.modules.institutes.models import Company, Country, Institute, Region
from app.modules.planning.models import ServiceSession
from app.modules.services.models import Service, ServiceCategory
from app.modules.tickets.models import QueueTicket, TicketLine
from app.shared.ids import new_id
from app.shared.responses import ok
from app.shared.time import utcnow

router = APIRouter(prefix="/dev", tags=["dev"])

DEMO_INSTITUTE_ID = "demo-institute-geneve"


@router.post("/init-demo-data")
def init_demo_data(db: Session = Depends(get_db)):
    """Seed minimal pour tester le MVP localement."""
    company = db.get(Company, "demo-company-flowpilot")
    if not company:
        company = Company(
            id="demo-company-flowpilot",
            name="FlowPilot Demo",
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

    institute = db.get(Institute, DEMO_INSTITUTE_ID)
    if not institute:
        institute = Institute(
            id=DEMO_INSTITUTE_ID,
            region_id=region.id,
            name="FlowPilot Genève Demo",
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
            db.add(ServiceCategory(id=category_id, name=name, code=code))

    db.flush()

    services = [
        ("svc-aisselles", "cat-epilation", "Aisselles", 10, 10, 9.90, 15.00, False, False),
        ("svc-sourcils", "cat-epilation", "Sourcils", 10, 10, 9.90, 15.00, False, False),
        ("svc-jambes-completes", "cat-epilation", "Jambes complètes", 20, 20, 24.90, 35.00, False, False),
        ("svc-semi-main", "cat-manucure", "Semi permanent mains", 30, 30, 29.90, 39.00, False, False),
        ("svc-beaute-pieds", "cat-manucure", "Beauté des pieds", 40, 40, 39.90, 49.00, False, False),
        ("svc-soin-profond", "cat-soins", "Soin profond", 50, 50, 59.90, 79.00, False, False),
        ("svc-lpg-corps", "cat-soins", "LPG corps", 45, 45, 59.90, 79.00, True, True),
    ]

    for service_id, category_id, name, duration_min, duration_max, price_member, price_passage, requires_machine, requires_appointment in services:
        service = db.get(Service, service_id)
        if not service:
            db.add(
                Service(
                    id=service_id,
                    category_id=category_id,
                    name=name,
                    duration_min=duration_min,
                    duration_max=duration_max,
                    price_member=price_member,
                    price_passage=price_passage,
                    requires_machine=requires_machine,
                    requires_appointment=requires_appointment,
                    status="active",
                )
            )
        else:
            service.duration_min = duration_min
            service.duration_max = duration_max
            service.requires_machine = requires_machine
            service.requires_appointment = requires_appointment
            service.status = "active"
            db.add(service)

    db.flush()

    employees = [
        ("emp-angela", "Angela", "A01"),
        ("emp-camille", "Camille", "C01"),
        ("emp-clara", "Clara", "C02"),
        ("emp-assya", "Assya", "A02"),
    ]

    for employee_id, first_name, code in employees:
        employee = db.get(Employee, employee_id)
        if not employee:
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
        else:
            employee.institute_id = institute.id
            employee.first_name = first_name
            employee.code = code
            employee.skills = ["EPILATION", "MANUCURE", "SOINS"]
            if employee.status not in {"busy", "pause", "absent", "offline"}:
                employee.status = "available"
            db.add(employee)

    if not get_user_by_email(db, "accueil@flowpilot.demo"):
        db.add(
            User(
                id="user-accueil-demo",
                email="accueil@flowpilot.demo",
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
            "login": "accueil@flowpilot.demo",
            "password": "demo1234",
        },
        "Données de démonstration initialisées",
    )


@router.post("/reset-demo")
def reset_demo(institute_id: str = DEMO_INSTITUTE_ID, db: Session = Depends(get_db)):
    """Nettoie uniquement les données opérationnelles de démonstration."""
    _reset_operational_data(db, institute_id)
    return ok({"institute_id": institute_id}, "Journée de démonstration réinitialisée")


@router.post("/create-demo-day")
def create_demo_day(institute_id: str = DEMO_INSTITUTE_ID, db: Session = Depends(get_db)):
    """Crée une journée réaliste pour présenter le planning sans manipulation manuelle."""
    init_demo_data(db)
    _reset_operational_data(db, institute_id)

    now = utcnow().replace(second=0, microsecond=0)

    demo_items = [
        {
            "ticket_number": "D-001",
            "employee_id": "emp-angela",
            "service_id": "svc-sourcils",
            "ticket_status": "completed",
            "session_status": "completed",
            "start_offset": -70,
            "duration": 10,
        },
        {
            "ticket_number": "D-002",
            "employee_id": "emp-camille",
            "service_id": "svc-semi-main",
            "ticket_status": "in_progress",
            "session_status": "in_progress",
            "start_offset": -12,
            "duration": 30,
        },
        {
            "ticket_number": "D-003",
            "employee_id": "emp-clara",
            "service_id": "svc-aisselles",
            "ticket_status": "in_progress",
            "session_status": "in_progress",
            "start_offset": -18,
            "duration": 10,
        },
    ]

    for item in demo_items:
        ticket = _create_ticket_with_line(
            db=db,
            institute_id=institute_id,
            ticket_number=item["ticket_number"],
            service_id=item["service_id"],
            status=item["ticket_status"],
            employee_id=item["employee_id"],
            arrival_time=now + timedelta(minutes=item["start_offset"] - 3),
        )
        line = db.scalars(select(TicketLine).where(TicketLine.ticket_id == ticket.id)).first()
        start_time = now + timedelta(minutes=item["start_offset"])
        planned_end_time = start_time + timedelta(minutes=item["duration"])
        session = ServiceSession(
            id=new_id("sess"),
            ticket_line_id=line.id if line else None,
            institute_id=institute_id,
            employee_id=item["employee_id"],
            service_id=item["service_id"],
            start_time=start_time,
            planned_end_time=planned_end_time,
            real_end_time=planned_end_time if item["session_status"] == "completed" else None,
            duration_minutes=item["duration"],
            status=item["session_status"],
        )
        db.add(session)

    waiting_services = [
        ("D-004", "svc-jambes-completes", now - timedelta(minutes=4)),
        ("D-005", "svc-beaute-pieds", now - timedelta(minutes=1)),
    ]
    for ticket_number, service_id, arrival_time in waiting_services:
        _create_ticket_with_line(
            db=db,
            institute_id=institute_id,
            ticket_number=ticket_number,
            service_id=service_id,
            status="waiting",
            employee_id=None,
            arrival_time=arrival_time,
        )

    appointment_service = db.get(Service, "svc-lpg-corps") or db.get(Service, "svc-soin-profond")
    if appointment_service:
        db.add(
            Appointment(
                id=new_id("appt"),
                institute_id=institute_id,
                service_id=appointment_service.id,
                employee_id="emp-assya",
                customer_name="Mme Martin",
                phone="",
                start_time=now + timedelta(minutes=15),
                end_time=now + timedelta(minutes=15 + appointment_service.duration_min),
                status="scheduled",
                notes="Créé par la journée de test",
            )
        )
        db.add(
            Appointment(
                id=new_id("appt"),
                institute_id=institute_id,
                service_id=appointment_service.id,
                employee_id="emp-angela",
                customer_name="Mme Rossi",
                phone="",
                start_time=now - timedelta(minutes=95),
                end_time=now - timedelta(minutes=50),
                status="completed",
                notes="RDV terminé visible dans l'historique planning",
            )
        )

    for employee_id in ["emp-angela", "emp-camille", "emp-clara", "emp-assya"]:
        employee = db.get(Employee, employee_id)
        if employee:
            employee.status = "busy" if employee_id in {"emp-camille", "emp-clara"} else "available"
            db.add(employee)

    db.commit()
    return ok(
        {
            "institute_id": institute_id,
            "scenario": "demo-day",
            "active_sessions": 2,
            "waiting_tickets": 2,
            "appointments": 2,
        },
        "Journée de test créée",
    )


def _reset_operational_data(db: Session, institute_id: str) -> None:
    ticket_ids = select(QueueTicket.id).where(QueueTicket.institute_id == institute_id)

    db.execute(delete(ServiceSession).where(ServiceSession.institute_id == institute_id))
    db.execute(delete(TicketLine).where(TicketLine.ticket_id.in_(ticket_ids)))
    db.execute(delete(QueueTicket).where(QueueTicket.institute_id == institute_id))
    db.execute(delete(Appointment).where(Appointment.institute_id == institute_id))

    employees = db.scalars(select(Employee).where(Employee.institute_id == institute_id)).all()
    for employee in employees:
        if employee.status not in {"absent", "offline"}:
            employee.status = "available"
            db.add(employee)

    db.commit()


def _create_ticket_with_line(
    db: Session,
    institute_id: str,
    ticket_number: str,
    service_id: str,
    status: str,
    employee_id: str | None,
    arrival_time,
) -> QueueTicket:
    service = db.get(Service, service_id)
    duration = service.duration_min if service else 10
    price = float(service.price_member or service.price_passage or 0) if service else 0

    ticket = QueueTicket(
        id=new_id("ticket"),
        institute_id=institute_id,
        ticket_number=ticket_number,
        status=status,
        arrival_time=arrival_time,
        estimated_start_time=None,
        assigned_employee_id=employee_id,
        created_by_id="demo-seed",
    )
    db.add(ticket)
    db.flush()

    db.add(
        TicketLine(
            id=new_id("line"),
            ticket_id=ticket.id,
            service_id=service_id,
            quantity=1,
            unit_price=price,
            total=price,
            duration_minutes=duration,
            revenue_category="care",
        )
    )
    db.flush()
    return ticket
