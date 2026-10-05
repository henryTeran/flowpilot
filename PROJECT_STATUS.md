CURRENT_PHASE = PHASE 5
CURRENT_CHECKPOINT = PHASE5B_DURABLE_RESERVATION_PRIMITIVES
STATUS = ACTIVE

GATES:
- Prior Phase 0-3 historical closures preserved.
- Phase 4 availability, assignment, waiting projection and replay-safe extensions = PASS at recorded scope.
- RESOURCE_CATALOG = PASS (tenant-scoped resource kinds, capabilities/status, manager configuration and durable events).
- SKILL_MATCHING = PASS (all ticket lines; assignment/start/booking; reservation-safe skill removal).
- RESOURCE_SCHEDULING / RESOURCE_CONFLICT = PARTIAL (requirements persisted; allocation remains Phase 5B).
- PRODUCTION_READY = NOT_VERIFIED.

TESTS:
- Backend: 156 passed, 9 opt-in PostgreSQL cases skipped on SQLite; one TestClient deprecation warning.
- PostgreSQL Phase 5 bundle: 3 passed (qualification race and SQLite/PostgreSQL migration round-trips with metadata parity).
- PostgreSQL Phase 4 scheduling races: 7 passed with the new schema.
- Frontend: 13 passed; production build passed.
- Resource allocation domain: 8 passed (deterministic capability/quantity matching, complete intervals, unknown occupancy, joint windows and boundaries).
- Reservation primitives: 3 passed (replay, cross-owner conflicts, release/rollback and overdue unknown occupancy).
- Migration b3d620a481f9: PostgreSQL upgrade/check passed; SQLite/PostgreSQL round-trip bundle 2 passed with metadata parity.
- Migration a1c935e720d4 preserves legacy employee JSON and deduplicates normalized skills; downgrade/re-upgrade passed.
- PostgreSQL upgrade head and alembic check passed in disposable validation database.
- JSDOM workflow checks are component evidence, not browser/tablet proof.
- Validation containers: flowpilot-phase4-validation (loopback 55434) and flowpilot-phase4-test-runner (read-only backend mount).

SECURITY:
- Configuration and employee creation require responsable_institut and exact tenant; reception may read configuration.
- Configuration and capacity writes share institute serialization; PostgreSQL assignment-versus-revocation race passed.
- Qualification changes cannot invalidate committed tickets, active sessions or appointments.
- Configured resource needs yield unknown capacity and reject assignment/start/booking until allocation is implemented.
- No provider or secret changes; BASE/JV separation preserved.

BLOCKERS:
- Browser/tablet validation = BLOCKED (CUA returned apps=[] and browsers=[]).
- No business decision blocks independent Phase 5 implementation.
- Appointment lifecycle concurrency audit and larger load remain open.

NEXT_STEP:
- PHASE5B: integrate tested resource matcher with durable reservations, lifecycle release, extension conflicts and shared capacity projection.
- Preserve browser gate as BLOCKED; do not claim complete Phase 4 or Phase 5 closure.
- Details: docs/architecture/RESOURCES_AND_SKILLS.md and FLOW_CAPACITY_ENGINE.md.

LAST_COMMITS:
- Current checkpoint: feat(resources): persist transactional resource reservations.
- a8b7420 feat(resources): add deterministic interval allocation core.
- da7a0f2 feat(resources): add tenant-scoped resources and qualification guards.
- a566a0e feat(queue): guide assignment with duration-aware feasibility.
- 5a20caf feat(planning): make service extensions durably replay safe.

WORKING_TREE:
- Checkpoint files reviewed and committed; inspect git status before next unit.
