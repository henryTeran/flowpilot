from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from pydantic import ValidationError
from fastapi import HTTPException
from sqlalchemy import select, func, event
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.base import interactions as journal, read_capabilities as base
from app.modules.base.models import InteractionOriginal
from app.modules.waitlist.originals import Envelope, fingerprint
from test_ticket_workflow import _bootstrap_reference_data
from test_postgres_scheduling_4d import postgres_flow

def exercise(engine, institute):
    actor = base.Principal(actor_id="manager", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        first = journal.begin(db, actor, institute, "resolve_intent", {"utterance": "Private source text", "selection": "chosen"})
        second = journal.begin(db, actor, institute, "read", {"root_id": "selected"})
        stopped = journal.finish(db, actor, institute, first, 400, {"error": "Never retain private exception details"})
        done = journal.finish(db, actor, institute, second, 200, {"result": "proof"})
        report = journal.audit(db, actor, institute, 0, 2)
        assert report.total == 4 and report.unresolved_attempts == 0 and report.originals == (first, second)
        assert journal.audit(db, actor, institute, 2, 2).originals == (stopped, done)
        assert "Private source text" not in str(report.model_dump())
        assert stopped.original["response_fingerprint"] is None and done.original["response_fingerprint"] == fingerprint({"result": "proof"})
        assert done.original["previous_id"] == stopped.original["id"] and done.original["previous_fingerprint"] == stopped.fingerprint
        for wrong in [first.model_copy(update={"fingerprint": "0"*64}), Envelope(original={**first.original, "action": "execute"}, fingerprint=first.fingerprint)]:
            with pytest.raises(HTTPException): journal.finish(db, actor, institute, wrong, 200, None)
        with pytest.raises(HTTPException): journal.finish(db, actor, institute, first, 200, None)
        pending = journal.begin(db, actor, institute, "execute", {"operation_id": "explicit"})
        assert journal.audit(db, actor, institute).unresolved_attempts == 1
        with pytest.raises(HTTPException): journal.finish(db, actor.model_copy(update={"actor_id": "peer"}), institute, pending, 200)
        assert journal.audit(db, actor, institute).unresolved_attempts == 1
        failed = journal.finish(db, actor, institute, pending, 503, {"secret": "provider detail"})
        assert failed.original["kind"] == "failed" and failed.original["response_fingerprint"] is None
        with pytest.raises(HTTPException): journal.begin(db, actor, "foreign", "read", {})
        with pytest.raises(ValidationError): journal.begin(db, actor, institute, "generated_sql", {})
        row = db.get(InteractionOriginal, first.original["id"])
        altered = deepcopy(row.original); altered["request_fingerprint"] = "0"*64
        row.original = altered; row.fingerprint = fingerprint(altered); db.commit()
        # Even an outer rehash cannot rewrite a predecessor behind later entries.
        with pytest.raises(HTTPException): journal.audit(db, actor, institute, 4, 2)
        with pytest.raises(HTTPException): journal.begin(db, actor, institute, "read", {})

def test_sqlite_interleaved_attempts_results_privacy_and_full_chain(client):
    institute, *_ = _bootstrap_reference_data(client)
    exercise(main_module.engine, institute)

def test_postgres_interleaved_attempts_results_privacy_and_full_chain(postgres_flow):
    exercise(postgres_flow[0], postgres_flow[1])

def test_postgres_concurrent_append_and_completion_serialize(postgres_flow):
    engine, institute, *_ = postgres_flow
    actor = base.Principal(actor_id="manager", institute_id=institute, role="responsable_institut")
    barrier = Barrier(2)
    def begin(index):
        with Session(engine) as db:
            barrier.wait(); return journal.begin(db, actor, institute, "read", {"index": index})
    with ThreadPoolExecutor(2) as pool: attempts = list(pool.map(begin, [0, 1]))
    barrier = Barrier(2)
    def finish(index):
        with Session(engine) as db:
            barrier.wait()
            try: return journal.finish(db, actor, institute, attempts[0], 200, {"result": index})
            except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(2) as pool: results = list(pool.map(finish, [0, 1]))
    assert sum(isinstance(v, Envelope) for v in results) == 1 and 400 in results
    with Session(engine) as db:
        report = journal.audit(db, actor, institute)
        assert report.total == 3 and report.unresolved_attempts == 1
        assert [e.original["sequence"] for e in report.originals] == [1, 2, 3]

def test_postgres_outcome_failure_retains_pending_attempt(postgres_flow):
    engine, institute, *_ = postgres_flow
    actor = base.Principal(actor_id="manager", institute_id=institute, role="responsable_institut")
    with Session(engine) as db:
        attempt = journal.begin(db, actor, institute, "read", {})
        def fail(session, context, instances):
            if any(isinstance(v, InteractionOriginal) and v.attempt_id for v in session.new): raise RuntimeError("Outcome storage failed")
        event.listen(db, "before_flush", fail)
        with pytest.raises(RuntimeError): journal.finish(db, actor, institute, attempt, 200, {"result": "already available"})
        event.remove(db, "before_flush", fail)
        report = journal.audit(db, actor, institute)
        assert report.total == 1 and report.unresolved_attempts == 1
        assert db.scalar(select(func.count()).select_from(InteractionOriginal)) == 1

def test_invalid_principals_never_access_database():
    actor = base.Principal(actor_id="manager", institute_id="own", role="responsable_institut")
    class NoDatabase:
        def rollback(self): pass
        def scalar(self, *args): raise AssertionError("Invalid principal reached SQL")
    for principal, institute in [(actor, "foreign"), (actor.model_copy(update={"actor_id": "bad\nactor"}), "own"),
            (actor.model_copy(update={"role": "unregistered"}), "own")]:
        with pytest.raises(HTTPException): journal.begin(NoDatabase(), principal, institute, "read", {})
