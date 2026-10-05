CURRENT_PHASE = PHASE 4
CURRENT_CHECKPOINT = PHASE4D_CONFLICT_SERIALIZATION
STATUS = ACTIVE

GATES:
- PHASE_0 / PHASE_1 / PHASE_2 / PHASE_3 = CLOSED (historical checkpoints preserved)
- AVAILABILITY_ENGINE = PARTIAL (existing 17 tests pass; future-slot and overdue-session semantics need audit)
- QUEUE_ASSIGNMENT = PARTIAL (duration-aware writes already implemented; API router now registered; reservations reflected in options)
- PHASE4B_API_RECONCILIATION = PASS
- WAITING_TIME_ENGINE = PASS (Phase 4 inputs: durations, FIFO, explicit reservations, active sessions, appointments and operational status; resources/skills follow Phase 5)
- PHASE4C_WAITING_PROJECTION = PASS
- SERVICE_EXTENSION_IMPACT = PARTIAL (extension exists; conflict impact needs implementation)
- CONFLICT_HANDLING = PARTIAL (assignment/start/booking/extension collision checks and 6 PostgreSQL races pass; appointment lifecycle and availability helpers remain to audit)
- PHASE4D_CONFLICT_SERIALIZATION = PASS
- PHASE4_POSTGRES_MIGRATIONS = PASS (upgrade/downgrade/re-upgrade and alembic check, disposable PostgreSQL 15)
- PHASE4_POSTGRES_TWO_WORKER_RACES = PASS (6 actual parallel transaction tests; not a load test)
- PRODUCTION_READY = NOT_VERIFIED

TESTS:
- Backend baseline: 106 passed.
- Backend after Phase 4D: 120 passed; 6 opt-in PostgreSQL tests skipped in local SQLite run.
- Separate PostgreSQL run: 6 passed (test_postgres_scheduling_4d.py); random test schemas cleaned automatically.
- Extension boundary/atomic conflict test passes: failed writes do not change duration or event count.
- Waiting projection: 11 tests cover boundaries, multiple appointments, FIFO/ties, parallel workers, reservations, quantity snapshots, tenant isolation, overdue/paused unknown capacity, extension/finish recalculation and dashboard consistency.
- Targeted scheduling API + assignment options: 12 passed.
- Command from backend: DATABASE_URL=sqlite:///:memory: ../.venv/Scripts/python.exe -m pytest tests -q
- API tests exercise registered availability/pool/options routes, reservations, missing/foreign tickets, RBAC and tenant isolation.
- Warning: Starlette TestClient httpx deprecation.
- PostgreSQL validation uses Docker runner because local psycopg2 installation needs pg_config.
- Disposable containers: flowpilot-phase4-validation (loopback 55434), flowpilot-phase4-test-runner (read-only backend mount).
- FLOWPILOT_TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:5432/flowpilot_validation inside runner.
- Deep PostgreSQL load = DEFERRED; no 1000-operation stress claim.
- Browser/tablet UX = DEFERRED (previous CSS-only claims do not prove browser validation).

SECURITY:
- Missing/foreign ticket options return generic 404; unauthorized roles/tenants return 403.
- Writes retain institute serialization and full-duration appointment checks.
- No new schema, provider or secret changes.

LAST_COMMITS:
- Current checkpoint: fix(scheduling): serialize booking and extension capacity conflicts
- 864a063 feat(scheduling): project live appointment-aware queue waiting times
- bdd4cf4 fix(scheduling): expose reservation-aware scheduling APIs
- 8c4b699 chore(status): close Phase 4B and prepare Phase 4C
- 23334d9 feat(scheduling): implement queue assignment options with service duration awareness (Phase 4B)
- 2b8d8d3 feat(scheduling): implement deterministic availability engine with 17 tests

BLOCKERS:
- No blocking business decision identified for current checkpoint.
- PostgreSQL concurrency now exercised directly; larger load and extension replay safety remain open.

NEXT_STEP:
- PHASE4E: reconcile unknown/chained availability semantics, extension replay safety, and browser UX.
- Phase 4 remains open until these gates pass; then proceed to resources/skills.
- Implementation and validation details: docs/architecture/FLOW_CAPACITY_ENGINE.md.
- Waiting projection is read-only; it does not authorize assignment or start.
- Assigned tickets reserve their employee first; unassigned tickets retain FIFO with stable employee-ID tie breaks.
- Unknown remaining durations or unavailable assigned employees yield no estimate, never an invented fallback.

WORKING_TREE:
- Checkpoint files reviewed and committed; inspect git status before next unit.
