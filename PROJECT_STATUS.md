CURRENT_PHASE = PHASE 7
CURRENT_CHECKPOINT = PHASE7C_COMMITTED_DATABASE_REVISION_DELIVERY
STATUS = ACTIVE

GATES:
- Historical Phase 0-3 closures preserved.
- Phase 4 functional checks = PASS at recorded scope; browser/tablet remains BLOCKED.
- PHASE5 = CLOSED: RESOURCE_SCHEDULING / SKILL_MATCHING / RESOURCE_CONFLICT = PASS.
- PHASE6 = CLOSED: HYBRID_BOOKING / BOOKING_CREATE / BOOKING_MOVE / BOOKING_CANCEL / RESOURCE_RESERVATION / COEXISTENCE_WALKIN_BOOKING = PASS.
- Customer reservation scope is the canonical named-customer authenticated operator workflow; no public portal was specified or claimed.
- PHASE7 = IN_PROGRESS: real-time synchronization and reconnection remain unverified; TABLET_UX is BLOCKED.
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Revision delivery checkpoint: backend 192 passed, 15 opt-in PostgreSQL cases skipped locally; PostgreSQL race bundle 14 passed.
- Migration f7b012e542ad: upgrade/check and SQLite/PostgreSQL round-trip/model parity passed.
- Revision transaction/rollback/replay checks passed; ASGI committed queue-to-WebSocket delivery and tenant scope checks passed.
- PostgreSQL revision/migration bundle: 3 passed; atomic concurrent counter increments and schema parity passed.
- Frontend: 18 tests and production build passed; reconnect, heartbeat timeout, resynchronization, stale socket and cleanup simulations pass.
- WebSocket tenant/role and connection lifecycle bundle: 7 passed; these do not prove committed-change synchronization.
- Backend full suite: 184 passed, 14 opt-in PostgreSQL cases skipped locally; one TestClient deprecation warning.
- Phase 6 audit targeted checks: 5 passed; final overdue session/appointment creation/movement recovery: 2 passed.
- PostgreSQL final booking/resource regression bundle: 12 passed (including competing moves, duplicate creation and cross-operation resource races).
- Previous qualification race passed separately; these focused races are not a load test.
- Booking migrations through e6a901df431c: SQLite/PostgreSQL round-trips, legacy preservation and metadata parity passed; PostgreSQL upgrade/check passed.
- Frontend: 15 tests and production build passed; JSDOM is component evidence only.
- Gate matrices: docs/architecture/RESOURCES_AND_SKILLS.md and HYBRID_BOOKING.md.

INVARIANTS:
- Deterministic institute-scoped capacity; BASE/JV separation preserved.
- Booking routes require exact operator tenant; configuration writes require manager.
- Moves preserve old state on failure; booking/resource/history changes share a transaction.
- Creation replay recovers one booking/resource/event; history omits contact/free-text data.
- Overdue occupancy has unknown remaining duration and blocks creation/movement until resolved.

BLOCKERS:
- Browser/tablet validation unavailable: CUA apps=[] and browsers=[]. Independent development continues.
- Deep load and production readiness remain unverified; no business decision blocks Phase 7.

NEXT_STEP:
- PHASE7D: live two-worker WebSocket delivery/reconnect validation and stale REST response protection.
- Server sends committed revision changes through one-second database polling. Do not infer browser or load PASS from ASGI/component checks.
- Preserve TABLET_UX as BLOCKED until actual browser evidence is available.

LAST_COMMITS:
- Current: feat(realtime): notify planning clients of committed database revisions.
- f4c1eb7 feat(realtime): reconnect planning clients and resynchronize after transport loss.
- f1b968e fix(realtime): isolate scoped connections and tolerate closed transports.
- 9ec32ce fix(booking): reject unknown overdue capacity and close functional booking gates.
- 18bccd5 feat(booking): recover customer reservations after retried creation.
- f00068c feat(booking): persist transactional booking change history.

WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before the next unit.
