"""Controlled queue/resource states only in the runner-owned disposable DB."""
import os
import sys
import json
from pathlib import Path
from tempfile import gettempdir
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

directory = Path(os.environ["FLOWPILOT_BROWSER_DIRECTORY"]).resolve()
if (directory.parent != Path(gettempdir()).resolve() or not directory.name.startswith("flowpilot-browser-")
        or not (directory / ".flowpilot-browser-owner").is_file() or not (directory / "browser.sqlite").is_file()):
    raise RuntimeError("Existing owned browser fixture required")
suffix, mode = sys.argv[1:3]
if suffix not in ("desktop", "tablet-landscape") or mode not in ("seed", "maintenance", "unqualified", "restore", "counts"):
    raise RuntimeError("Known browser fixture operation required")
os.environ.update(DATABASE_URL="sqlite:///"+(directory / "browser.sqlite").as_posix(), APP_ENV="test",
    SECRET_KEY="isolated-slot-fixture-only", AUTO_CREATE_SCHEMA_ON_STARTUP="false")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
from app.main import app
from app.database.session import engine
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.modules.tickets.models import QueueTicket, TicketLine
from app.modules.appointments.models import Appointment
from app.modules.employees.models import Employee
from app.modules.services.models import Service
from app.modules.resources.models import Resource, ResourceRequirement, ServiceRequirement, EmployeeSkill, ResourceReservation

institute, employee = "demo-institute-geneve", "emp-angela"
service, machine, room, skill = ("slot-care-"+suffix, "slot-machine-"+suffix, "slot-room-"+suffix, "slot-skill-"+suffix)
now = datetime.now(timezone.utc)
with Session(engine) as db:
    if mode == "seed":
        category = db.scalar(select(Service.category_id))
        for identifier, name, requires in ((service, "Slot care "+suffix, False), (machine, "Slot missing resources "+suffix, True)):
            db.add(Service(id=identifier, category_id=category, name=name, duration_min=20, duration_max=20, status="active", requires_machine=requires))
        db.add(ServiceRequirement(institute_id=institute, service_id=service, skill_code=skill))
        db.add(ResourceRequirement(id="slot-need-"+suffix, institute_id=institute, service_id=service, kind="room", capability=skill, quantity=1))
        db.add(Resource(id=room, institute_id=institute, name="Slot room "+suffix, kind="room", capabilities=[skill], status="active"))
        for e in db.scalars(select(Employee).where(Employee.institute_id==institute)):
            e.status="unavailable"
        db.get(Employee,employee).status="available"
        db.add(EmployeeSkill(institute_id=institute,employee_id=employee,skill_code=skill))
        ticket="slot-prior-"+suffix
        db.add(QueueTicket(id=ticket,institute_id=institute,ticket_number=ticket,status="waiting",arrival_time=now-timedelta(minutes=1)))
        db.flush()
        db.add(TicketLine(id=ticket+"-line",ticket_id=ticket,service_id=service,quantity=1,duration_minutes=20))
        db.add(Appointment(id="slot-block-"+suffix,institute_id=institute,employee_id=employee,service_id=service,customer_name="Owned source fixture",
            start_time=now+timedelta(minutes=25),end_time=now+timedelta(days=3),status="confirmed"))
    elif mode == "maintenance":
        db.get(Resource,room).status="maintenance"
    elif mode == "unqualified":
        db.get(Employee,employee).skills=[]
        db.delete(db.get(EmployeeSkill,(employee,skill)))
    elif mode == "restore":
        db.get(Resource,room).status="active"
        if db.get(EmployeeSkill,(employee,skill)) is None:
            db.add(EmployeeSkill(institute_id=institute,employee_id=employee,skill_code=skill))
    db.commit()
    counts={name:db.scalar(select(func.count()).select_from(model).where(model.institute_id==institute))
        for name,model in (("tickets",QueueTicket),("appointments",Appointment),("reservations",ResourceReservation))}
    local=now.astimezone(ZoneInfo("Europe/Zurich")).date()
    print(json.dumps(dict(service=service,machine=machine,short=(local+timedelta(days=1)).isoformat(),long=(local+timedelta(days=5)).isoformat(),counts=counts)))
engine.dispose()
