CURRENT_PHASE = PHASE 6
CURRENT_CHECKPOINT = PHASE6B_BOOKING_CONFIRMATION
STATUS = ACTIVE

GATES:
- Prior Phase 0-3 historical closures preserved.
- Phase 4 functional checks = PASS at recorded scope; browser/tablet = BLOCKED.
- RESOURCE_SCHEDULING = PASS (explicit resource quantity/capability matching; complete intervals; queue/booking lifecycle; joint projections).
- SKILL_MATCHING = PASS (all ticket services; assignment/start/booking; commitment-safe configuration).
- RESOURCE_CONFLICT = PASS (shared institute serialization; three actual resource races; failure rollback).
- PHASE5 = CLOSED for canonical functional gates; load and browser proof are separate, unverified gates.
- PHASE6 = IN_PROGRESS (create/cancel/confirm/resource lifecycle and booked/execution facts present; move and customer reservation remain).
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Confirmation and booking lifecycle: 4 passed (replay, booked/resource preservation, foreign tenant, missing/cancelled state rejection).
- Planning/availability/prior-migration regression: 20 passed.
- Phase 6A lifecycle/migration bundle: 4 passed, 1 PostgreSQL case skipped locally.
- PostgreSQL migration/race bundle: 5 passed; seeded legacy appointment migration rerun: 2 passed (SQLite/PostgreSQL).
- Migration c4e780bd219a upgrade/check passed; booked facts preserved and historical actual times remain null.
- Last full backend suite: 177 passed, 12 opt-in PostgreSQL cases skipped on SQLite.
- New resource tenant/quantity/multi-service boundary cases: 2 passed (not a claim of a new full-suite run).
- PostgreSQL race bundle: 11 passed, including 3 resource races across different employees.
- Availability/atomicity targeted bundle: 29 passed; resource lifecycle/fault/joint bundle: 13 passed.
- Migration b3d620a481f9: SQLite/PostgreSQL round-trips and metadata parity passed; PostgreSQL alembic check passed.
- Frontend last tested: 13 passed and production build passed; no frontend changes in subsequent backend checkpoints.
- TestClient deprecation warning remains; no test failure outstanding.
- Resource gate matrix: docs/architecture/RESOURCES_AND_SKILLS.md.

INVARIANTS:
- Explicit configuration only; no inferred skills/machine types; BASE/JV separation preserved.
- Resource/skill writes require manager and exact tenant; reception may read.
- Full-ticket snapshot duration and distinct resource quantities are enforced.
- Resource/employee commitments and operational changes share transaction boundaries.
- Overdue unknown occupancy produces no fabricated capacity or estimate.

BLOCKERS:
- Browser/tablet validation unavailable: CUA apps=[] and browsers=[]. Independent development continues.
- Deep load and production readiness are unverified; no business decision blocks Phase 6.

NEXT_STEP:
- PHASE6C: safe booking modification/movement and customer reservation; confirmation and booked/execution timestamps now implemented.
- Validate coexistence with assigned walk-ins and resource reservations under the institute lock.

LAST_COMMITS:
- Current: feat(booking): confirm appointments without duplicating reservations.
- 75d2aae feat(booking): preserve booked and actual appointment timestamps.
- d2ce8de test(resources): close functional resource and qualification gates.
- 9dcbe46 fix(scheduling): account for resources in service availability.
- b3197c2 feat(scheduling): project joint employee and resource waiting capacity.

WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before next unit.
