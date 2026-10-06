"""Opt-in loopback HTTP/WebSocket test with two owned Uvicorn processes.

Uses the disposable PostgreSQL fixture; never starts against a user schema.
Client lifecycle simulations live in frontend tests, separate from this protocol test.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.realtime.revisions import mark_planning_changed
from app.modules.resources.models import ResourceReservation
from app.shared.time import utcnow
from test_postgres_scheduling_4d import postgres_flow
from test_realtime_tenant_isolation_2b import _ws_token


@contextmanager
def live_worker(engine, tmp_path, label):
    with engine.connect() as connection:
        schema = connection.scalar(text("SELECT current_schema()"))
    assert schema.startswith("fp_test_")
    url = engine.url.update_query_dict({"options": f"-csearch_path={schema}"})
    environment = dict(os.environ, DATABASE_URL=url.render_as_string(hide_password=False),
                       AUTO_CREATE_SCHEMA_ON_STARTUP="false", APP_ENV="test",
                       SECRET_KEY=settings.SECRET_KEY, ALGORITHM=settings.ALGORITHM)
    # Holding the listener until the child inherits it avoids a free-port race.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    log_path = tmp_path / f"{label}.log"
    with log_path.open("w+") as log:
        process = None
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--fd", str(listener.fileno()),
                 "--log-level", "warning"],
                pass_fds=(listener.fileno(),), env=environment,
                cwd=Path(__file__).resolve().parents[1], stdout=log, stderr=log,
            )
            listener.close()
            address = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 20
            with httpx.Client(timeout=0.5) as client:
                while True:
                    assert process.poll() is None, f"{label} exited during startup"
                    try:
                        if client.get(address + "/ready").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    assert time.monotonic() < deadline, f"{label} startup timed out"
                    time.sleep(0.05)
            yield address, process.pid
        finally:
            listener.close()
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def test_cross_process_commits_and_reconnected_rest_resynchronization(postgres_flow, tmp_path):
    if os.name == "nt":
        pytest.skip("Inherited POSIX listener required; run in the disposable Linux test runner")
    connect = pytest.importorskip("websockets.sync.client").connect
    engine, institute, employee, service = postgres_flow
    with Session(engine) as db:
        origin = db.get(Institute, institute)
        foreign = "live-foreign-institute"
        db.add(Institute(id=foreign, region_id=origin.region_id, name="Foreign", city="Test"))
        db.commit()
    token = _ws_token(institute_id=institute)
    headers = {"Authorization": f"Bearer {token}"}
    with live_worker(engine, tmp_path, "writer") as (writer, writer_pid), \
            live_worker(engine, tmp_path, "reader") as (reader, reader_pid):
        assert writer_pid != reader_pid
        ws_url = reader.replace("http://", "ws://") + f"/ws/institutes/{institute}/planning?token={token}"
        foreign_url = reader.replace("http://", "ws://") + f"/ws/institutes/{foreign}/planning?token={_ws_token(institute_id=foreign)}"
        with httpx.Client(base_url=writer, headers=headers, timeout=5) as http:
            with connect(ws_url, open_timeout=5) as ws, connect(foreign_url, open_timeout=5) as other:
                response = http.post("/api/v1/tickets", json={"institute_id": institute, "service_id": service})
                assert response.status_code == 200, response.text
                first = json.loads(ws.recv(timeout=5))
                assert set(first) == {"event", "revision"}
                assert first["event"] == "planning.changed"
                with pytest.raises(TimeoutError):
                    other.recv(timeout=1.2)
                with Session(engine) as db:
                    db.get(Employee, employee).status = "pause"
                    db.flush()
                    db.rollback()
                    mark_planning_changed(db, foreign)
                    db.commit()
                assert json.loads(other.recv(timeout=5))["event"] == "planning.changed"
                with pytest.raises(TimeoutError):
                    ws.recv(timeout=1.2)
            # A committed write while offline is recovered by REST after reconnect;
            # a new write then proves the replacement transport receives notices.
            offline = http.post("/api/v1/tickets", json={"institute_id": institute, "service_id": service})
            assert offline.status_code == 200
            with connect(ws_url, open_timeout=5) as reconnected:
                snapshot = http.get(f"/api/v1/tickets/waiting?institute_id={institute}")
                assert snapshot.status_code == 200
                assert offline.json()["id"] in {ticket["id"] for ticket in snapshot.json()}
                assert http.post("/api/v1/tickets", json={"institute_id": institute, "service_id": service}).status_code == 200
                recovered = json.loads(reconnected.recv(timeout=5))
                assert recovered["event"] == "planning.changed"
                assert recovered["revision"] > first["revision"]


def test_live_actions_recalculate_employee_resource_and_checkout_state(postgres_flow, tmp_path):
    if os.name == "nt":
        pytest.skip("Inherited POSIX listener required; run in the disposable Linux test runner")
    connect = pytest.importorskip("websockets.sync.client").connect
    engine, institute, employee, service = postgres_flow
    token = _ws_token(institute_id=institute)
    headers = {"Authorization": f"Bearer {token}"}
    with live_worker(engine, tmp_path, "actions") as (writer, _), live_worker(engine, tmp_path, "board") as (reader, _):
        with httpx.Client(base_url=writer, headers=headers, timeout=5) as commands, \
                httpx.Client(base_url=reader, headers=headers, timeout=5) as board:
            manager_headers = {"Authorization": f"Bearer {_ws_token('responsable_institut', institute)}"}
            assert commands.put(f"/api/v1/gift-cards/institutes/{institute}/settings", headers=manager_headers, json={"currency": "CHF"}).status_code == 200
            prefix = f"/api/v1/resources/institutes/{institute}"
            assert commands.post(prefix, headers=manager_headers, json={"name": "Live room", "kind": "room"}).status_code == 200
            assert commands.patch(prefix + f"/services/{service}/requirements", headers=manager_headers,
                                  json={"skills": [], "resources": [{"kind": "room"}]}).status_code == 200
            ws_url = reader.replace("http://", "ws://") + f"/ws/institutes/{institute}/planning?token={token}"
            with connect(ws_url, open_timeout=5) as ws:
                revision = 0
                def change(method, path, payload=None):
                    nonlocal revision
                    response = commands.request(method, "/api/v1" + path, json=payload)
                    assert response.status_code == 200, response.text
                    notice = json.loads(ws.recv(timeout=5))
                    assert notice["event"] == "planning.changed" and notice["revision"] > revision
                    revision = notice["revision"]
                    return response.json()
                def read(path):
                    response = board.get("/api/v1" + path)
                    assert response.status_code == 200, response.text
                    return response.json()
                def availability():
                    return next(row for row in read(f"/planning/institutes/{institute}/availability")["employees"]
                                if row["employee_id"] == employee)
                def tickets():
                    return read(f"/tickets/waiting?institute_id={institute}")
                def reservation(ticket_id):
                    from sqlalchemy import select
                    with Session(engine) as db:
                        row = db.scalar(select(ResourceReservation).where(ResourceReservation.ticket_id == ticket_id))
                        return row.status, row.end_time

                change("PATCH", f"/employees/{employee}/status", {"status": "pause"})
                assert availability()["employee_status"] == "pause" and availability()["available_at"] is None
                change("PATCH", f"/employees/{employee}/status", {"status": "available"})
                assert availability()["available_at"] is not None
                first = change("POST", "/tickets", {"institute_id": institute, "service_id": service})
                second = change("POST", "/tickets", {"institute_id": institute, "service_id": service})
                change("PATCH", f"/tickets/{first['id']}/assign", {"employee_id": employee})
                assert reservation(first["id"])[0] == "reserved"
                session = change("POST", "/planning/sessions/start", {"ticket_id": first["id"], "employee_id": employee, "service_id": service})
                row = availability()
                assert row["employee_status"] == "busy" and row["active_session_id"] == session["id"]
                assert reservation(first["id"])[0] == "in_use"
                extended = change("PATCH", f"/planning/sessions/{session['id']}/extend", {"minutes": 5, "idempotency_key": "live-extension"})
                expected_end = datetime.fromisoformat(extended["planned_end_time"])
                assert expected_end > datetime.fromisoformat(session["planned_end_time"])
                assert datetime.fromisoformat(availability()["available_at"]) == expected_end
                queued = next(ticket for ticket in tickets() if ticket["id"] == second["id"])
                assert datetime.fromisoformat(queued["estimated_start_time"]) >= expected_end
                sessions = next(row for row in read(f"/planning/institutes/{institute}/today")["rows"] if row["employee_id"] == employee)["sessions"]
                assert next(row for row in sessions if row["id"] == session["id"])["planned_end_time"] == extended["planned_end_time"]
                change("PATCH", f"/planning/sessions/{session['id']}/finish")
                assert availability()["active_session_id"] is None and availability()["employee_status"] == "available"
                assert reservation(first["id"])[0] == "released"
                assert next(ticket for ticket in tickets() if ticket["id"] == first["id"])["status"] == "ready_for_checkout"
                change("PATCH", f"/tickets/{first['id']}/checkout/start", {"employee_id": employee})
                assert commands.patch(f"/api/v1/tickets/{first['id']}/currency", json={"currency": "CHF", "reason": "Explicit live invoice currency"}).status_code == 200
                change("PATCH", f"/tickets/{first['id']}/checkout/pay", {"employee_id": employee, "payment_method": "cb"})
                assert first["id"] not in {ticket["id"] for ticket in tickets()}
                report = read(f"/tickets/chiffres?institute_id={institute}")
                assert report["currency"] == "CHF" and report["totals"]["total"] > 0

                booking_payload = {"institute_id": institute, "employee_id": employee, "service_id": service,
                                   "customer_name": "Live booking", "start_time": (utcnow() + timedelta(minutes=1)).isoformat()}
                booking = change("POST", "/appointments", booking_payload)
                booking_path = f"/appointments/{booking['id']}"
                assert change("PATCH", booking_path + "/confirm")["status"] == "confirmed"
                assert change("PATCH", booking_path + "/arrive")["status"] == "arrived"
                change("PATCH", booking_path + "/start")
                assert availability()["active_appointment_id"] == booking["id"]
                finished = change("PATCH", booking_path + "/complete")
                assert availability()["active_appointment_id"] is None
                checkout = finished["checkout_ticket_id"]
                assert next(ticket for ticket in tickets() if ticket["id"] == checkout)["status"] == "ready_for_checkout"
                change("PATCH", f"/tickets/{checkout}/checkout/pay", {"employee_id": employee, "payment_method": "cb"})
                assert checkout not in {ticket["id"] for ticket in tickets()}
                absent = change("POST", "/appointments", {**booking_payload, "start_time": (utcnow() + timedelta(hours=2)).isoformat()})
                assert change("PATCH", f"/appointments/{absent['id']}/no-show")["status"] == "no_show"
                assert next(row for row in read(f"/appointments?institute_id={institute}") if row["id"] == absent["id"])["status"] == "no_show"
