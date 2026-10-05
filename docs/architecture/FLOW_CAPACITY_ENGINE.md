# Flow and capacity engine — Phase 4 checkpoint

The official queue estimate is computed by `scheduling/waiting_domain.py` from
tenant-scoped facts loaded by `scheduling/waiting_service.py`. No provider or LLM
participates in these calculations.

- Ticket duration uses line snapshots multiplied by quantity, not current catalog duration.
- Explicit assignments reserve their employee before unassigned projections.
- Unassigned tickets retain arrival-time/ID order. Equal employee start times use employee ID.
- A complete service must fit before the next appointment; otherwise its projected start
  moves past that appointment. Adjacent intervals may touch without conflicting.
- Active service end times include extensions. Paused, absent, offline, overdue and
  unexplained busy employees have no known capacity and cannot produce a fabricated estimate.
- Waiting-ticket API reads and the dashboard recalculate from current facts. Stored
  creation-time estimates remain historical snapshots rather than live truth.
- An unknown queue estimate makes the dashboard average unknown, rather than substituting
  elapsed waiting or excluding unknown tickets from the average.

Estimates do not authorize writes. Assignment/start revalidate full-duration conflicts
under the institute lock. Booking creation and service extension use the same PostgreSQL
institute lock. New bookings respect assigned walk-in reservations; extensions reject
appointment overlaps atomically before changing duration or adding an event.

## Executable evidence

From `backend`, run the normal suite against disposable SQLite fixtures:

```powershell
$env:DATABASE_URL='sqlite:///:memory:'
../.venv/Scripts/python.exe -m pytest tests -q
```

For PostgreSQL race tests, set `FLOWPILOT_TEST_POSTGRES_URL` to a validation database
whose account may create schemas, then run:

```text
python -m pytest tests/test_postgres_scheduling_4d.py -q
```

Each PostgreSQL test creates and removes its own random schema. Tests cover competing
assignments, starts, duplicate arrivals, overlapping bookings, extension versus booking,
and assignment versus booking. These are simultaneous two-worker races, not a load test.
Without an explicit PostgreSQL URL the tests are skipped, never counted as concurrency PASS.

On an empty disposable PostgreSQL database, also run `alembic upgrade head`,
`alembic check`, `alembic downgrade base`, and `alembic upgrade head`. Never run the
downgrade check on a user database.

## Remaining gates

Phase 4A helper semantics (unknown availability and chained future appointments) need
reconciliation. Extension request replay safety, actual tablet/browser validation and
larger concurrent load remain open. Resources and skills are Phase 5 inputs; the current
projection does not claim to account for them. Production readiness is unverified.
