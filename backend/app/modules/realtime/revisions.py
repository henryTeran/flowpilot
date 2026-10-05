"""Transactional invalidation markers, shared by all workers through the database."""
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.modules.realtime.models import PlanningRevision

SCOPED_TABLES = {
    "institutes", "employees", "queue_tickets", "queue_events", "service_sessions",
    "session_extensions", "appointments", "booking_events", "resources",
    "resource_reservations", "resource_configuration_events", "employee_skills",
    "service_requirements", "resource_requirements",
}


def mark_planning_changed(db: Session, institute_id: str):
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise RuntimeError("Planning revisions require PostgreSQL or SQLite")
    statement = insert(PlanningRevision).values(institute_id=institute_id, revision=1)
    db.execute(statement.on_conflict_do_update(index_elements=["institute_id"],
                set_={"revision": PlanningRevision.revision + 1}))


@event.listens_for(Session, "before_flush")
def collect_planning_changes(db, flush_context, instances):
    from app.modules.tickets.models import QueueTicket
    changed = set(db.new) | set(db.dirty) | set(db.deleted)
    scopes = set()
    new_tickets = {row.id: row.institute_id for row in db.new if isinstance(row, QueueTicket)}
    for row in changed:
        if row in db.dirty and row not in db.deleted and not db.is_modified(row, include_collections=False):
            continue
        table = getattr(row, "__tablename__", "")
        if table in SCOPED_TABLES:
            identifier = row.id if table == "institutes" else row.institute_id
            if identifier:
                scopes.add(identifier)
        elif table == "ticket_lines":
            identifier = new_tickets.get(row.ticket_id)
            if identifier is None:
                identifier = db.scalar(select(QueueTicket.institute_id).where(QueueTicket.id == row.ticket_id))
            if identifier:
                scopes.add(identifier)
        elif table in {"services", "service_categories"}:
            db.info["planning_catalog_changed"] = True
    db.info.setdefault("planning_changed_scopes", set()).update(scopes)


@event.listens_for(Session, "after_flush_postexec")
def persist_planning_changes(db, flush_context):
    scopes = db.info.pop("planning_changed_scopes", set())
    if db.info.pop("planning_catalog_changed", False):
        from app.modules.institutes.models import Institute
        scopes.update(db.scalars(select(Institute.id)).all())
    for institute_id in sorted(scopes):
        mark_planning_changed(db, institute_id)


@event.listens_for(Session, "after_rollback")
def clear_rolled_back_changes(db):
    db.info.pop("planning_changed_scopes", None)
    db.info.pop("planning_catalog_changed", None)
