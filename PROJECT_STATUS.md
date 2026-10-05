CURRENT_PHASE = PHASE 8
CURRENT_CHECKPOINT = PHASE8A_PACKAGE_BACKEND_LIFECYCLE
STATUS = ACTIVE

GATES:
- Historical Phase 0-3 closures preserved.
- Phase 4 functional scope PASS; browser/tablet remains open.
- PHASE5 = CLOSED: RESOURCE_SCHEDULING / SKILL_MATCHING / RESOURCE_CONFLICT = PASS.
- PHASE6 = CLOSED: HYBRID_BOOKING / BOOKING_CREATE / BOOKING_MOVE / BOOKING_CANCEL / RESOURCE_RESERVATION / COEXISTENCE_WALKIN_BOOKING = PASS.
- PHASE7 = PARTIAL: LIVE_BOARD / REALTIME_SYNC / LIVE_RECALCULATION PASS at authenticated two-process protocol scope; actual browser RECONNECT and TABLET_UX remain open.
- PHASE8 = IN_PROGRESS: PACKAGES backend lifecycle implemented; UI/reversal/customer binding remain. MEMBERSHIPS / GIFTCARDS / LOYALTY = PENDING.
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Full backend run: 195 passed, 19 opt-in PostgreSQL cases skipped locally; one TestClient deprecation warning.
- Final local package/checkout/revision regressions: 12 passed, 1 PostgreSQL case skipped.
- PostgreSQL final package suite: 3 passed, including two preloaded stale balances competing for the last session.
- PostgreSQL package/booking-move/revision regression bundle: 6 passed.
- Package migrations: SQLite/PostgreSQL round-trip/model-parity bundle with package tests: 5 passed; PostgreSQL upgrade/check passed.
- Package HTTP checks cover role/tenant, expiry, customer match, replay, failed-flush rollback, covered checkout pricing and payment recovery.
- Live two-process PostgreSQL suite: 2 passed; each walk-in/booking action revision followed by reader-side REST checks.
- Last frontend validation: 23 tests and production build passed; JSDOM is component evidence only.
- Gate details: docs/architecture/RESOURCES_AND_SKILLS.md, HYBRID_BOOKING.md, REALTIME_OPERATIONS.md and COMMERCE.md.

INVARIANTS:
- Deterministic institute-scoped business truth; BASE/JV separation preserved.
- Booking/resource/history/checkout handoff is transactional; legacy finished bookings are not rebilled.
- Package balance, price coverage and immutable redemption history share one transaction and institute lock.
- Customer references follow existing ticket customer_id; CRM profiles and public self-service are not claimed.
- Entitlement issuance does not claim a paid package sale or external payment settlement.
- Demo reset cannot erase commercial redemption-linked tickets.

BLOCKERS:
- Browser/tablet unavailable: last CUA inventory apps=[] and browsers=[]. Independent development continues.
- Deep load, external settlement and production readiness remain unverified.

NEXT_STEP:
- PHASE8B: package reversal and operator/customer/booking integration; then memberships, gift cards and loyalty.
- Numbering follows detailed Master Plan sections 29-47 (Phase 8 Commerce, Phase 12 CRM); condensed Phase 8 Client 360 label is stale.
- Preserve open browser/tablet gates; do not infer production readiness from protocol/component checks.

LAST_COMMITS:
- Current: feat(commerce): add scoped package balances and checkout consumption.
- b3d941d test(operations): verify live actions and recalculation across servers.
- 16d0fcc feat(booking): hand completed reservations to checkout transactionally.
- 3ff886c fix(operations): ignore action completions after institute changes.
- 42c6654 test(realtime): prove delivery across live server processes.

WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before the next unit.
