"""Observed care and original-rule fixtures only in the owned disposable DB."""
import os
import sys
import json
from pathlib import Path
from tempfile import gettempdir
from datetime import datetime, timedelta, timezone

directory=Path(os.environ["FLOWPILOT_BROWSER_DIRECTORY"]).resolve()
if (directory.parent!=Path(gettempdir()).resolve() or not directory.name.startswith("flowpilot-browser-")
        or not (directory/".flowpilot-browser-owner").is_file() or not (directory/"browser.sqlite").is_file()):
    raise RuntimeError("Existing owned browser fixture required")
suffix,mode=sys.argv[1:3]
if suffix not in ("desktop","tablet-landscape") or mode not in ("seed","disabled","future","restore","book","counts"):
    raise RuntimeError("Known owned fixture operation required")
os.environ.update(DATABASE_URL="sqlite:///"+(directory/"browser.sqlite").as_posix(),APP_ENV="test",SECRET_KEY="isolated-rebooking-fixture-only",AUTO_CREATE_SCHEMA_ON_STARTUP="false")
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"backend"))
from app.main import app
from app.database.session import engine
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from app.modules.customers.models import Customer
from app.modules.tickets.models import QueueTicket,TicketLine
from app.modules.planning.models import ServiceSession
from app.modules.appointments.models import Appointment
from app.modules.services.models import Service
from app.modules.resources.models import ResourceReservation
from app.modules.crm import automation_originals,lifecycle_originals
from app.modules.crm.models import EventCaptureOriginal,EventRevision

institute,employee="demo-institute-geneve","emp-angela"
stem="rebook-native-"+suffix
now=datetime.now(timezone.utc)
with Session(engine) as db:
    service=db.scalar(select(Service.id))
    if mode=="seed":
        for n in range(27):
            cid=f"{stem}-{n:02}"
            completed=now-timedelta(days=1 if n==26 else 3)
            db.add(Customer(id=cid,institute_id=institute,display_name="Owned return fixture",phone=None,search_name="owned return fixture",phone_digits="",
                idempotency_key=cid,creation_fingerprint="0"*64,created_at=now-timedelta(days=4),created_by="fixture-registered"))
            db.add(QueueTicket(id=cid+"-ticket",institute_id=institute,customer_id=cid,ticket_number=cid,status="paid",arrival_time=completed-timedelta(minutes=30),paid_at=completed))
        absent=stem+"-no-care"
        db.add(Customer(id=absent,institute_id=institute,display_name="Owned missing care fixture",phone=None,search_name="owned missing care fixture",phone_digits="",
            idempotency_key=absent,creation_fingerprint="0"*64,created_at=now-timedelta(days=4),created_by="fixture-registered"))
        db.flush()
        for n in range(27):
            cid=f"{stem}-{n:02}"
            db.add(TicketLine(id=cid+"-line",ticket_id=cid+"-ticket",service_id=service,quantity=1,duration_minutes=30))
        db.flush()
        for n in range(27):
            cid=f"{stem}-{n:02}"
            completed=now-timedelta(days=1 if n==26 else 3)
            db.add(ServiceSession(id=cid+"-care",institute_id=institute,employee_id=employee,service_id=service,ticket_line_id=cid+"-line",
                start_time=completed-timedelta(minutes=30),planned_end_time=completed,real_end_time=completed,duration_minutes=30,status="completed"))
        db.add(Appointment(id=stem+"-booked",institute_id=institute,customer_id=stem+"-00",customer_name="Owned already booked fixture",employee_id=employee,service_id=service,
            start_time=now+timedelta(hours=1),end_time=now+timedelta(hours=2),status="scheduled"))
        db.commit()
        comm=[dict(channel=channel,purpose=purpose,permission="granted" if purpose=="service_follow_up" and channel=="email" else "refused" if purpose=="marketing" else "unknown",
            evidence="Explicit owned permission evidence" if purpose=="marketing" or channel=="email" else None)
            for channel in ("email","sms") for purpose in ("service_follow_up","marketing")]
        lifecycle_originals.create(db,institute,stem+"-01",lifecycle_originals.Declaration.model_validate(dict(declaration=dict(institute_id=institute,customer_id=stem+"-01",
            birthday=None,birthday_evidence=None,communications=comm),previous_id=None,reason="Owned explicit permissions",idempotency_key=stem+"-life")),"fixture-permission-manager")
    if mode in ("seed","disabled","future","restore"):
        previous=automation_originals.current(db,institute)
        triggers=("birthday","post_service","rebooking","inactivity","package_expiry","subscription_renewal")
        rules=[dict(trigger=t,enabled=t=="rebooking" and mode!="disabled",offset_us=str(30*86400000000 if mode=="future" else 2*86400000000) if t=="rebooking" else "1" if t=="inactivity" else "0") for t in triggers]
        automation_originals.create(db,institute,automation_originals.PolicyCreate.model_validate(dict(policy=dict(institute_id=institute,rules=rules),
            previous_policy_id=previous.id if previous else None,reason="Owned declared return rule "+mode,idempotency_key=stem+"-rule-"+mode)),"fixture-rule-manager")
    if mode=="book":
        db.add(Appointment(id=stem+"-new-return",institute_id=institute,customer_id=stem+"-01",customer_name="Owned return suppression fixture",employee_id=employee,service_id=service,
            start_time=now+timedelta(hours=3),end_time=now+timedelta(hours=4),status="confirmed"))
        db.commit()
    counts={name:db.scalar(select(func.count()).select_from(model).where(model.institute_id==institute)) for name,model in
        (("tickets",QueueTicket),("appointments",Appointment),("reservations",ResourceReservation),("event_captures",EventCaptureOriginal),("event_revisions",EventRevision))}
    print(json.dumps(dict(customer=stem+"-01",unknown=stem+"-02",booked=stem+"-00",counts=counts)))
engine.dispose()
