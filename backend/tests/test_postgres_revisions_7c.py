from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.institutes.models import Institute
from app.modules.realtime.models import PlanningRevision
from app.modules.realtime.revisions import mark_planning_changed
from test_postgres_scheduling_4d import postgres_flow, race


def test_two_workers_cannot_lose_committed_revision_increments(postgres_flow):
    engine, institute, _, _ = postgres_flow
    with Session(engine) as db:
        original = db.scalar(select(PlanningRevision.revision).where(PlanningRevision.institute_id == institute))
    def change(db):
        mark_planning_changed(db, institute)
        db.commit()
        return db.get(Institute, institute)
    assert all(status == "ok" for status, _ in race(engine, [change, change]))
    with Session(engine) as db:
        assert db.scalar(select(PlanningRevision.revision).where(PlanningRevision.institute_id == institute)) == original + 2
