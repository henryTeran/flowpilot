CURRENT_PHASE = PHASE 6
CURRENT_CHECKPOINT = PHASE6F_CUSTOMER_RESERVATION_REPLAY
STATUS = ACTIVE

GATES:
- Prior Phase 0-3 historical closures preserved.
- Phase 4 functional checks = PASS at recorded scope; browser/tablet = BLOCKED.
- RESOURCE_SCHEDULING = PASS (explicit resource quantity/capability matching; complete intervals; queue/booking lifecycle; joint projections).
- SKILL_MATCHING = PASS (all ticket services; assignment/start/booking; commitment-safe configuration).
- RESOURCE_CONFLICT = PASS (shared institute serialization; three actual resource races; failure rollback).
- PHASE5 = CLOSED for canonical functional gates; load and browser proof are separate, unverified gates.
- PHASE6 = IN_PROGRESS (named-customer reservation, safe move/modification, operator controls and durable history present; final gate audit remains).
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Reservation replay checkpoint: full backend 182 passed, 14 skipped; PostgreSQL regression races 11 passed plus booking duplicate/move races 2 passed.
- Customer booking creation recovery and lifecycle passed; client key retry tests: frontend 15 passed and build passed.
- PostgreSQL duplicate booking/move races: 2 passed; migration round-trip/parity: 2 passed; upgrade/check passed.
- History checkpoint full backend: 182 passed, 13 skipped; final targeted fault test passed.
- Booking history lifecycle/migration: 7 passed, 1 PostgreSQL case skipped locally; final move fault injection: 2 passed.
- PostgreSQL migration and move race: 3 passed; upgrade/check passed for d5f890ce320b.
- History records operator and operational before/after facts; no customer contact/free-text data copied; retries/no-op writes create no duplicates.
- Frontend: 14 tests passed; production build passed. Booking editor component verifies confirmation, failed-move retry and update payload.
- Full backend: 182 passed, 13 opt-in PostgreSQL cases skipped locally; final strict-tenant targeted rerun passed.
- Booking move/confirmation/lifecycle: 6 passed; final strict-tenant move/confirmation checks: 3 passed.
- PostgreSQL two-booking move race: 1 passed; exactly one target room reservation, unchanged losing booking.
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
- PHASE6G: hybrid booking gate audit; named-customer operator reservations now recoverable via durable replay keys.
- The canonical plan does not specify a public customer portal; reservation evidence covers the authenticated operator workflow.
- Validate coexistence with assigned walk-ins and resource reservations under the institute lock.

LAST_COMMITS:
- Current: feat(booking): recover customer reservations after retried creation.
- f00068c feat(booking): persist transactional booking change history.
- 77a99a9 feat(booking): expose appointment editing and confirmation controls.
- fe66101 feat(booking): move appointments with atomic capacity revalidation.
- a1e262f feat(booking): confirm appointments without duplicating reservations.
- 75d2aae feat(booking): preserve booked and actual appointment timestamps.
- d2ce8de test(resources): close functional resource and qualification gates.
- 9dcbe46 fix(scheduling): account for resources in service availability.
- b3197c2 feat(scheduling): project joint employee and resource waiting capacity.

WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before next unit.
