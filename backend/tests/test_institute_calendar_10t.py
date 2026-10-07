from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

import app.main as main_module
from app.modules.appointments import service as appointments
from app.modules.appointments.models import Appointment
from app.modules.institutes.calendar import day_bounds
from app.modules.institutes.models import Institute
from app.modules.planning.models import ServiceSession
from app.modules.planning.repository import list_sessions_for_day
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers


@pytest.mark.parametrize('civil,hours,start_hour', [
    (date(2026, 3, 29), 23, 23), (date(2026, 10, 25), 25, 22),
])
def test_civil_bounds_follow_both_dst_changes(client, civil, hours, start_hour):
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        db.get(Institute, institute).timezone = 'Europe/Zurich'
        db.commit()
        start, end = day_bounds(db, institute, civil)
        assert start.date() == civil - timedelta(days=1)
        assert start.hour == start_hour
        assert end - start == timedelta(hours=hours)
        assert day_bounds(db, institute, start) == (start, end)
        assert day_bounds(db, institute, end)[0] == end


def test_agenda_local_midnight_explicit_date_scope_and_planning_edges(client, monkeypatch):
    institute, employees, services = _bootstrap_reference_data(client)
    now = datetime(2026, 10, 6, 22, 30, tzinfo=timezone.utc)
    monkeypatch.setattr(appointments, 'utcnow', lambda: now)
    with Session(main_module.engine) as db:
        db.get(Institute, institute).timezone = 'Europe/Zurich'
        start, end = day_bounds(db, institute, now)
        common = dict(institute_id=institute, employee_id=employees[0]['id'], service_id=services[0]['id'])
        for name, instant in [('before', start-timedelta(microseconds=1)), ('lower', start),
                              ('future', now+timedelta(hours=2)), ('upper', end)]:
            db.add(Appointment(id=name, **common, customer_name=name,
                start_time=instant, end_time=instant+timedelta(minutes=15), status='no_show'))
        for name, a, b, status in [('ended', start-timedelta(minutes=15), start, 'completed'),
                                 ('overlap', start-timedelta(minutes=15), start+timedelta(minutes=1), 'completed'),
                                 ('next', end, end+timedelta(minutes=15), 'completed'),
                                 ('active-old', start-timedelta(days=2), start-timedelta(days=1), 'in_progress')]:
            db.add(ServiceSession(id=name, **common, start_time=a, planned_end_time=b,
                duration_minutes=15, status=status))
        db.commit()
        assert {row.id for row in list_sessions_for_day(db, institute, now)} == {'overlap', 'active-old'}
    headers = _auth_headers(institute_id=institute)
    path = f'/api/v1/appointments?institute_id={institute}'
    result = client.get(path, headers=headers)
    assert result.status_code == 200
    assert {row['id'] for row in result.json()} == {'lower', 'future'}
    assert {row['id'] for row in client.get(path+'&day=2026-10-08', headers=headers).json()} == {'upper'}
    assert client.get(path+'&day=not-a-date', headers=headers).status_code == 422
    assert client.get(path+'&day=9999-12-31', headers=headers).status_code == 400
    assert client.get(path+'&day=0001-01-01', headers=headers).status_code == 400
    assert client.get(path+'&day=2026-10-08', headers=_auth_headers(institute_id='other')).status_code == 403
    assert client.get(path+'&day=2026-10-08', headers=_auth_headers('collaboratrice', institute)).status_code == 403


def test_invalid_legacy_zone_uses_explicit_utc_day(client):
    institute, _, _ = _bootstrap_reference_data(client)
    with Session(main_module.engine) as db:
        db.get(Institute, institute).timezone = 'invalid/legacy'
        db.commit()
        start, end = day_bounds(db, institute, datetime(2026, 10, 6, 23, 30, tzinfo=timezone.utc))
        assert start == datetime(2026, 10, 6, tzinfo=timezone.utc)
        assert end == start + timedelta(days=1)
