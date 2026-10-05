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

Extension API calls require `idempotency_key` (1–120 characters, nonblank).
The UI retains the key for retries and clears it after the write succeeds, before
refreshing views. Per-session submission guards prevent overlapping UI requests.
`session_extensions` records the before/after end times, minutes, requester and
occurrence time in the same transaction as the session change and queue event.
Matching retries return the current session without repeating the effect; a changed
duration with the same key is rejected. Authorization precedes replay handling.

The queue UI reads duration-aware assignment options for its selected ticket and
institute. Loading or failed checks disable assignment/start and expose a retry.
Conflicting employees remain visible with an explanation; eligible employees form
the quick choices. Selecting a planning-queue ticket opens the existing drawer and
preselects a feasible employee, so starting normally takes two actions.
Late responses from a previous ticket or institute cannot replace current options.
These options improve the UI; backend writes still revalidate concurrent state.

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
assignment versus booking, and duplicate extension requests. These are simultaneous
two-worker races, not a load test.
Without an explicit PostgreSQL URL the tests are skipped, never counted as concurrency PASS.

On an empty disposable PostgreSQL database, also run `alembic upgrade head`,
`alembic check`, `alembic downgrade base`, and `alembic upgrade head`. Never run the
downgrade check on a user database.

## Remaining gates

Availability helpers and planning now share unknown-capacity and chained-window semantics.
Extension request replay safety is validated, including persistence-failure rollback.
Actual tablet/browser validation and larger concurrent load remain open.
No CUA browser surface was available during this checkpoint; JSDOM and build checks
are not browser/tablet evidence. Phase 5A adds explicit qualifications to assignment,
booking, start and waiting projection. Configured resource requirements currently
produce unknown capacity until Phase 5B implements allocation. See
`RESOURCES_AND_SKILLS.md`. Production readiness is unverified.
