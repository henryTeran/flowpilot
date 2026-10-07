"""Explicitly enabled standalone CRM runner; journal stores no credential."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import threading
from typing import Annotated
from uuid import uuid4
from pydantic import AwareDatetime, Field
from starlette.requests import Request
from app.core.permissions import require_ticket_manager
from app.modules.crm.event_worker import PassRequest, dispatch
from app.modules.crm.metrics import Fact, Identifier
from app.modules.crm.policies import Reason


class Journal(Fact):
    version: Annotated[int, Field(strict=True, ge=1, le=1)] = 1
    institute_id: Identifier
    actor_id: Annotated[str, Field(min_length=1, max_length=160)]
    reason: Reason
    interval_seconds: Annotated[int, Field(strict=True, gt=0, le=2147483647)]
    cycle_key: Identifier
    after: Identifier | None
    next_due_at: AwareDatetime | None
    failed_customer_ids: tuple[Identifier, ...]
    completed_cycles: Annotated[int, Field(strict=True, ge=0)]


def authorize(token, institute):
    request = Request({"type":"http","headers":[(b"authorization",("Bearer "+token).encode())]})
    user = require_ticket_manager(request)
    if user.get("role") != "responsable_institut" or user.get("institute_id") != institute:
        raise ValueError("Worker requires a signed manager of the configured institute")
    actor = user.get("sub")
    if not isinstance(actor,str) or not actor.strip(): raise ValueError("Worker requires an identified actor")
    return actor


def save(path, journal):
    # Write and fsync a same-directory temporary file before atomic replacement.
    temporary = path.with_name(path.name+".tmp-"+uuid4().hex)
    try:
        with temporary.open("x",encoding="utf-8") as stream:
            json.dump(journal.model_dump(mode="json"),stream,separators=(",",":"))
            stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists(): temporary.unlink()


@contextmanager
def lease(path):
    # OS locks release on process death; no stale PID-based deletion is needed.
    with path.with_name(path.name+".lock").open("a+b") as stream:
        stream.seek(0,2)
        if stream.tell()==0:stream.write(b"1");stream.flush()
        stream.seek(0)
        if os.name=="nt":
            import msvcrt
            msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:yield
        finally:
            stream.seek(0)
            if os.name=="nt":msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)


def run(session_factory, institute, reason, interval_seconds, state_path, token_provider,
        stop, *, once=False, now=lambda:datetime.now(timezone.utc), dispatch_page=dispatch, notify=lambda _:None):
    path = Path(state_path).resolve()
    if not path.parent.is_dir(): raise ValueError("Worker journal directory must already exist")
    actor = authorize(token_provider(),institute)
    initial = Journal(institute_id=institute,actor_id=actor,reason=reason,interval_seconds=interval_seconds,
        cycle_key=uuid4().hex,after=None,next_due_at=None,failed_customer_ids=(),completed_cycles=0)
    with lease(path):
        journal = Journal.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else initial
        if (journal.institute_id,journal.actor_id,journal.reason,journal.interval_seconds) != (
            initial.institute_id,initial.actor_id,initial.reason,initial.interval_seconds):
            raise ValueError("Retained worker institute/actor/terms changed; journal cannot be silently reset")
        if not path.exists():save(path,journal)
        while not stop.is_set():
            if authorize(token_provider(),institute) != journal.actor_id:
                raise ValueError("Retained worker actor changed")
            if journal.next_due_at:
                delay=(journal.next_due_at-now()).total_seconds()
                if delay>0:
                    stop.wait(min(delay,1));continue
                journal=Journal.model_validate({**journal.model_dump(),"cycle_key":uuid4().hex,
                    "after":None,"next_due_at":None,"failed_customer_ids":()})
                save(path,journal)
            result = dispatch_page(session_factory,institute,PassRequest(after=journal.after,
                reason=journal.reason,idempotency_key=journal.cycle_key),journal.actor_id)
            ids=[item.customer_id for item in result.items]
            if (result.institute_id!=institute or result.after!=journal.after or len(ids)>50
                or ids!=sorted(set(ids)) or any(journal.after is not None and i<=journal.after for i in ids)
                or result.next_after is not None and (not ids or result.next_after!=ids[-1])):
                raise ValueError("Worker page/cursor scope requires verification")
            failures=tuple(sorted(set(journal.failed_customer_ids)|{i.customer_id for i in result.items if i.failed}))
            complete=result.next_after is None
            journal=Journal.model_validate({**journal.model_dump(),"after":result.next_after,
                "failed_customer_ids":failures,"next_due_at":now()+timedelta(seconds=interval_seconds) if complete else None,
                "completed_cycles":journal.completed_cycles+int(complete)})
            save(path,journal)
            notify({"completed_cycles":journal.completed_cycles,"failed_customers":len(failures),"complete":complete})
            if once and complete:return journal
        return journal



def verify_schema(engine):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import text
    backend=Path(__file__).resolve().parents[3]
    config=Config(str(backend/"alembic.ini"));config.set_main_option("script_location",str(backend/"migrations"))
    expected=set(ScriptDirectory.from_config(config).get_heads())
    try:
        with engine.connect() as connection:actual=set(connection.scalars(text("SELECT version_num FROM alembic_version")))
    except Exception as error:raise RuntimeError("Worker requires an explicitly migrated database") from error
    if actual!=expected:raise RuntimeError("Worker database migration revision does not match this checkout")

def main():
    parser=argparse.ArgumentParser(description="Explicitly enabled internal CRM worker; no messages sent")
    parser.add_argument("--enable",action="store_true")
    parser.add_argument("--institute",required=True);parser.add_argument("--reason",required=True)
    parser.add_argument("--interval-seconds",required=True,type=int);parser.add_argument("--state",required=True)
    parser.add_argument("--once",action="store_true")
    args=parser.parse_args()
    if not args.enable:parser.error("Activation requires --enable")
    from app.core.config import settings
    settings.validate_runtime_security()
    authorize(os.environ.get("FLOWPILOT_CRM_WORKER_TOKEN",""),args.institute)
    import app.main  # Register the same complete model set as the API.
    from app.database.session import SessionLocal, engine
    verify_schema(engine)
    stop=threading.Event()
    import signal
    signal.signal(signal.SIGINT,lambda *_:stop.set())
    signal.signal(signal.SIGTERM,lambda *_:stop.set())
    result=run(SessionLocal,args.institute,args.reason,args.interval_seconds,args.state,
        lambda:os.environ.get("FLOWPILOT_CRM_WORKER_TOKEN",""),stop,once=args.once,
        notify=lambda result:print(json.dumps(result),flush=True))
    if args.once and result.failed_customer_ids:raise SystemExit(2)


if __name__=="__main__":main()
