CURRENT_PHASE = PHASE 4
CURRENT_CHECKPOINT = PHASE4F_EXTENSION_REPLAY
STATUS = ACTIVE

GATES:
- PHASE_0 / PHASE_1 / PHASE_2 / PHASE_3 = CLOSED (historical checkpoints preserved)
- AVAILABILITY_ENGINE = PASS (known free windows across all appointments; unknown paused/absent/offline/overdue/unexplained busy capacity; planning consumes same engine)
- PHASE4E_AVAILABILITY_WINDOWS = PASS
- QUEUE_ASSIGNMENT = PARTIAL (duration-aware writes already implemented; API router now registered; reservations reflected in options)
- PHASE4B_API_RECONCILIATION = PASS
- WAITING_TIME_ENGINE = PASS (Phase 4 inputs: durations, FIFO, explicit reservations, active sessions, appointments and operational status; resources/skills follow Phase 5)
- PHASE4C_WAITING_PROJECTION = PASS
- SERVICE_EXTENSION_IMPACT = PASS (live queue/dashboard recalculation, guarded appointment collisions, durable replay-safe extensions)
- PHASE4F_EXTENSION_REPLAY = PASS
- CONFLICT_HANDLING = PARTIAL (assignment/start/booking/extension collision checks and 7 PostgreSQL races pass; appointment lifecycle and availability helpers remain to audit)
- PHASE4D_CONFLICT_SERIALIZATION = PASS
- PHASE4_POSTGRES_MIGRATIONS = PASS (upgrade/downgrade/re-upgrade and alembic check, disposable PostgreSQL 15)
- PHASE4_POSTGRES_TWO_WORKER_RACES = PASS (7 actual parallel transaction tests; not a load test)
- PRODUCTION_READY = NOT_VERIFIED

TESTS:
- Backend baseline: 106 passed.
- Backend after Phase 4F: 137 passed; 7 opt-in PostgreSQL tests skipped in local SQLite run.
- Extension replay/fault/tenant/migration targeted bundle: 21 passed.
- Frontend: 10 tests passed; production build passed.
- New extension migration 8a4d71f0b2c9: PostgreSQL upgrade/downgrade/re-upgrade and model parity passed; SQLite migration/legacy-preservation tests passed.
- Availability/planning targeted regression: 45 passed; 10 new window/unknown-capacity cases.
- Separate PostgreSQL run: 7 passed (test_postgres_scheduling_4d.py); random test schemas cleaned automatically.
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
- Browser/tablet UX = BLOCKED (CUA getState returned apps=[] and browsers=[]; no actual browser surface available).
- UI assignment-feasibility integration still requires audit; this blocker does not prevent independent implementation.

SECURITY:
- Missing/foreign ticket options return generic 404; unauthorized roles/tenants return 403.
- Writes retain institute serialization and full-duration appointment checks.
- Extension replay requires a nonblank key; DB uniqueness/check constraints and institute lock preserve atomicity.
- Replay handling follows tenant/RBAC checks; requester and before/after times are durably recorded.
- No provider or secret changes.

LAST_COMMITS:
- Current checkpoint: feat(planning): make service extensions durably replay safe
- dfdfec5 fix(scheduling): preserve unknown capacity and chained availability windows
- ce0b36b fix(scheduling): serialize booking and extension capacity conflicts
- 864a063 feat(scheduling): project live appointment-aware queue waiting times
- bdd4cf4 fix(scheduling): expose reservation-aware scheduling APIs
- 8c4b699 chore(status): close Phase 4B and prepare Phase 4C
- 23334d9 feat(scheduling): implement queue assignment options with service duration awareness (Phase 4B)
- 2b8d8d3 feat(scheduling): implement deterministic availability engine with 17 tests

BLOCKERS:
- No blocking business decision identified for current checkpoint.
- PostgreSQL concurrency and extension replay now exercised directly; larger load remains open.
- Browser validation blocked by missing enabled browser surface; proceed with independent roadmap work.

NEXT_STEP:
- PHASE4G: integrate duration-aware assignment options into existing UI; then proceed to Phase 5 resources/skills with browser gate explicitly open.
- Phase 4 remains open until these gates pass; then proceed to resources/skills.
- Implementation and validation details: docs/architecture/FLOW_CAPACITY_ENGINE.md.
- Waiting projection is read-only; it does not authorize assignment or start.
- Assigned tickets reserve their employee first; unassigned tickets retain FIFO with stable employee-ID tie breaks.
- Unknown remaining durations or unavailable assigned employees yield no estimate, never an invented fallback.

WORKING_TREE:
- Checkpoint files reviewed and committed; inspect git status before next unit.
