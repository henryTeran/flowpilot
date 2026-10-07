"""Opt-in single-intent deployment command; never imported by application startup."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Literal
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from pydantic import StrictBool, model_validator
from app.core.config import settings
from app.modules.crm.metrics import Fact, Identifier
from app.modules.marketing import dispatch_intents, dispatch_outcomes, dispatch_worker, transport_registry
from app.shared.exceptions import business_error


class Command(Fact):
    institute_id: Identifier
    intent_id: Identifier
    expected_fingerprint: str
    execute: StrictBool = False

    @model_validator(mode="after")
    def exact_fingerprint(self):
        if not re.fullmatch(r"[a-f0-9]{64}", self.expected_fingerprint):
            raise ValueError("Exact retained SHA-256 fingerprint required")
        return self


class Report(Fact):
    institute_id: Identifier
    intent_id: Identifier
    request_fingerprint: str
    mode: Literal["test", "live"]
    operation: Literal["inspect", "submit_observed", "reconcile_observed", "terminal", "uncertain"]
    status: Literal["unobserved", "accepted", "rejected", "unknown"]
    outcome_id: Identifier | None
    delivery_confirmed: Literal[False] = False


def schema_ready(db):
    if db.get_bind().dialect.name != "postgresql":
        raise business_error("Deployment invocation requires PostgreSQL")
    scripts = ScriptDirectory(str(Path(__file__).resolve().parents[3] / "migrations"))
    expected = set(scripts.get_heads())
    actual = set(MigrationContext.configure(db.connection()).get_current_heads())
    if not expected or actual != expected:
        raise business_error("Deployment schema must match the exact checked-in heads")


def invoke(session_factory, command, resolve=None):
    command = Command.model_validate(command.model_dump())
    if settings.AUTO_CREATE_SCHEMA_ON_STARTUP:
        raise business_error("Deployment invocation requires automatic schema creation disabled")
    with session_factory() as db:
        schema_ready(db)
        intent = dispatch_intents.require(db, command.institute_id, command.intent_id)
        if intent.request_fingerprint != command.expected_fingerprint:
            raise business_error("Selected intent fingerprint differs from retained original")
        previous = dispatch_outcomes.current(db, command.institute_id, command.intent_id)
        if not command.execute:
            return Report(institute_id=command.institute_id, intent_id=intent.id,
                request_fingerprint=intent.request_fingerprint, mode=intent.submission.account.mode,
                operation="inspect", status=previous.request.result.status if previous else "unobserved",
                outcome_id=previous.id if previous else None)
        # Test-mode accounts never route into the live registry from this command.
        if intent.submission.account.mode != "live":
            raise business_error("Deployment execution requires an explicitly live account")
    resolver = transport_registry.resolver(session_factory) if resolve is None else resolve
    result = dispatch_worker.run(session_factory, command.institute_id, command.intent_id,
        "marketing-dispatch-worker", resolver)
    return Report(institute_id=command.institute_id, intent_id=intent.id,
        request_fingerprint=intent.request_fingerprint, mode=intent.submission.account.mode,
        operation=result.operation, status=result.outcome.request.result.status,
        outcome_id=result.outcome.id)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inspect one retained marketing intent; execution is explicit and opt-in.")
    parser.add_argument("--institute", required=True)
    parser.add_argument("--intent", required=True)
    parser.add_argument("--expected-fingerprint", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--receipt", help="New local JSON receipt path; required for execution, never overwritten")
    args = parser.parse_args(argv)
    handle = None
    try:
        command = Command(institute_id=args.institute, intent_id=args.intent,
            expected_fingerprint=args.expected_fingerprint, execute=args.execute)
        if args.execute and not args.receipt:
            raise ValueError("Execution requires an exclusive receipt file")
        if args.receipt:
            # Reserve output before any provider decision; refuse existing files/symlinks.
            descriptor = os.open(args.receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            handle = os.fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        from app.database.session import SessionLocal
        report = invoke(SessionLocal, command)
        output = json.dumps(report.model_dump(mode="json"), ensure_ascii=True, sort_keys=True) + "\n"
        if handle:
            handle.write(output); handle.flush(); os.fsync(handle.fileno())
        sys.stdout.write(output)
        return 2 if report.status == "unknown" else 0
    except Exception:
        # Credentials, account configuration, destinations and exception detail never print.
        sys.stderr.write("Marketing invocation failed. Inspect retained originals before retry; no automatic resubmission.\n")
        return 1
    finally:
        if handle: handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
