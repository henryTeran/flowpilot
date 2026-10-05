CURRENT_PHASE = PHASE 4
CURRENT_CHECKPOINT = PHASE4C_WAITING_PROJECTION
STATUS = ACTIVE

GATES:
- PHASE_0 / PHASE_1 / PHASE_2 / PHASE_3 = CLOSED (historical checkpoints preserved)
- AVAILABILITY_ENGINE = PARTIAL (existing 17 tests pass; future-slot and overdue-session semantics need audit)
- QUEUE_ASSIGNMENT = PARTIAL (duration-aware writes already implemented; API router now registered; reservations reflected in options)
- PHASE4B_API_RECONCILIATION = PASS
- WAITING_TIME_ENGINE = PASS (Phase 4 inputs: durations, FIFO, explicit reservations, active sessions, appointments and operational status; resources/skills follow Phase 5)
- PHASE4C_WAITING_PROJECTION = PASS
- SERVICE_EXTENSION_IMPACT = PARTIAL (extension exists; conflict impact needs implementation)
- CONFLICT_HANDLING = PARTIAL (assignment/start checks exist; extension and appointment concurrency need audit)
- PRODUCTION_READY = NOT_VERIFIED

TESTS:
- Backend baseline: 106 passed.
- Backend after Phase 4C: 119 passed (SQLite disposable fixtures).
- Waiting projection: 11 tests cover boundaries, multiple appointments, FIFO/ties, parallel workers, reservations, quantity snapshots, tenant isolation, overdue/paused unknown capacity, extension/finish recalculation and dashboard consistency.
- Targeted scheduling API + assignment options: 12 passed.
- Command from backend: DATABASE_URL=sqlite:///:memory: ../.venv/Scripts/python.exe -m pytest tests -q
- API tests exercise registered availability/pool/options routes, reservations, missing/foreign tickets, RBAC and tenant isolation.
- Warning: Starlette TestClient httpx deprecation.
- PostgreSQL runtime/concurrency = DEFERRED (local venv lacks psycopg2; previous status claims not reproduced).
- Browser/tablet UX = DEFERRED (previous CSS-only claims do not prove browser validation).

SECURITY:
- Missing/foreign ticket options return generic 404; unauthorized roles/tenants return 403.
- Writes retain institute serialization and full-duration appointment checks.
- No new schema, provider or secret changes.

LAST_COMMITS:
- Current checkpoint: feat(scheduling): project live appointment-aware queue waiting times
- bdd4cf4 fix(scheduling): expose reservation-aware scheduling APIs
- 8c4b699 chore(status): close Phase 4B and prepare Phase 4C
- 23334d9 feat(scheduling): implement queue assignment options with service duration awareness (Phase 4B)
- 2b8d8d3 feat(scheduling): implement deterministic availability engine with 17 tests

BLOCKERS:
- No blocking business decision identified for current checkpoint.
- PostgreSQL runtime evidence remains required; SQLite does not prove row-lock concurrency.

NEXT_STEP:
- PHASE4D: service-extension conflicts, availability semantics and PostgreSQL concurrency validation.
- Waiting projection is read-only; it does not authorize assignment or start.
- Assigned tickets reserve their employee first; unassigned tickets retain FIFO with stable employee-ID tie breaks.
- Unknown remaining durations or unavailable assigned employees yield no estimate, never an invented fallback.

WORKING_TREE:
- Checkpoint files reviewed and committed; inspect git status before next unit.
