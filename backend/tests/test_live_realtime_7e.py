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
from contextlib import contextmanager

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.employees.models import Employee
from app.modules.institutes.models import Institute
from app.modules.realtime.revisions import mark_planning_changed
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
