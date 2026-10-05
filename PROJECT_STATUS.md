CURRENT_PHASE = PHASE 8
CURRENT_CHECKPOINT = PHASE8L_GIFT_CARD_TENDERS
STATUS = ACTIVE

GATES:
- Historical Phase 0-3 closures preserved.
- Phase 4 functional scope PASS; browser/tablet remains open.
- PHASE5 = CLOSED: RESOURCE_SCHEDULING / SKILL_MATCHING / RESOURCE_CONFLICT = PASS.
- PHASE6 = CLOSED: HYBRID_BOOKING / BOOKING_CREATE / BOOKING_MOVE / BOOKING_CANCEL / RESOURCE_RESERVATION / COEXISTENCE_WALKIN_BOOKING = PASS.
- PHASE7 = PARTIAL: LIVE_BOARD / REALTIME_SYNC / LIVE_RECALCULATION PASS at authenticated two-process protocol scope; actual browser RECONNECT and TABLET_UX remain open.
- PHASE8 = IN_PROGRESS: PACKAGES / MEMBERSHIPS functional server/component scope PASS. GIFTCARDS issuance, currency, expiry, debit/reversal, remaining due and full/mixed closure implemented at API scope; management/cashier interface remains. LOYALTY = PENDING.
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Full backend tender foundation: 218 passed, 40 opt-in PostgreSQL cases skipped locally; one TestClient deprecation warning. Final additional multi-card and distinct-invoice checks are included in the targeted runs below.
- Gift tender final local checks: 6 passed, 3 opt-in races skipped. Final PostgreSQL gift/migration bundle: 11 passed; commercial benefit/customer regression bundle: 17 passed.
- Migration d7fa12cfe247: PostgreSQL upgrade/check, SQLite/PostgreSQL round-trip/model parity and nonempty payment-history downgrade refusal passed. Races include two distinct invoices using one cached balance, duplicate debit/reversal and reversal-versus-closure.
- Full backend currency foundation: 212 passed, 37 opt-in PostgreSQL cases skipped; final currency/catalog regression: 4 passed, 2 opt-in races skipped.
- Final PostgreSQL currency/migration bundle: 8 passed, including duplicate confirmation, confirmation/payment serialization and downgrade refusal. Migration c6e901bed136 upgrade/check and SQLite/PostgreSQL round-trip/model parity passed.
- Full backend issuance-foundation run: 208 passed, 35 opt-in PostgreSQL cases skipped locally; one TestClient deprecation warning.
- Subsequent gift/unbacked-payment/ticket regression: 16 passed, 2 opt-in races skipped. Gift/migration PostgreSQL bundle: 7 passed.
- Migration b5d890adc025: PostgreSQL upgrade/check, SQLite/PostgreSQL round-trip/model parity and nonempty downgrade refusal verified.
- Final local membership lifecycle checks: 2 passed, 5 opt-in PostgreSQL cases skipped.
- Membership/package/reversal PostgreSQL regression bundle: 18 passed; final benefit/revision checks: 6 passed in PostgreSQL runner (2 locally, 4 opt-in races skipped).
- Migration a4c789fcb914: PostgreSQL upgrade/check passed; SQLite/PostgreSQL round-trip/model parity and nonempty downgrade refusal verified.
- Package configuration replay/package/migration PostgreSQL bundle: 7 passed; final local replay guard test: 1 passed, 1 opt-in case skipped.
- Migration e2a567da97f2: PostgreSQL upgrade/check passed; SQLite/PostgreSQL round-trip/model parity and keyed downgrade refusal verified.
- Membership lifecycle/migration PostgreSQL bundle: 9 passed, including overlapping-grant prevention, replay, preloaded-expiry renewal races and replacement-versus-restart race.
- Migration f3b678eba803: PostgreSQL upgrade/check passed; SQLite/PostgreSQL round-trip/model parity and nonempty downgrade refusal verified.
- Checkout attachment/identity/reversal PostgreSQL regression bundle: 10 passed, including beneficiary/consumption and beneficiary/payment races.
- Final identity checks: 2 passed; identity/migration/reversal PostgreSQL-runner bundle: 9 passed.
- Migration d1f456c986e1: SQLite/PostgreSQL parity/round-trip and PostgreSQL upgrade/check passed.
- Package/reversal/migration PostgreSQL bundle: 10 passed; final reversal suite: 5 passed, including reversal/payment and duplicate-credit races.
- Migration c0e345b875d0: SQLite/PostgreSQL round-trip/model parity and PostgreSQL upgrade/check pass; reversed-history downgrade refusal verified on both databases.
- Final local package/checkout/revision regressions: 12 passed, 1 PostgreSQL case skipped.
- PostgreSQL final package suite: 3 passed, including two preloaded stale balances competing for the last session.
- PostgreSQL package/booking-move/revision regression bundle: 6 passed.
- Package migrations: SQLite/PostgreSQL round-trip/model-parity bundle with package tests: 5 passed; PostgreSQL upgrade/check passed.
- Package HTTP checks cover role/tenant, expiry, customer match, replay, failed-flush rollback, covered checkout pricing and payment recovery.
- Live two-process PostgreSQL suite: 2 passed; each walk-in/booking action revision followed by reader-side REST checks.
- Frontend: 34 tests and production build passed; membership configuration/grant/renewal retry, wallet serialization, uncertain-price blocking, disposed-context isolation, StrictMode reads and UTC date parity verified in JSDOM only.
- Gate details: docs/architecture/RESOURCES_AND_SKILLS.md, HYBRID_BOOKING.md, REALTIME_OPERATIONS.md and COMMERCE.md.

INVARIANTS:
- Deterministic institute-scoped business truth; BASE/JV separation preserved.
- Booking/resource/history/checkout handoff is transactional; legacy finished bookings are not rebilled.
- Package balance, price coverage and immutable redemption history share one transaction and institute lock.
- Checkout customer correction uses the same lock; active coverage and paid states prevent beneficiary changes.
- Membership grant/renewal uses registered scoped identities, snapshotted terms and transactional validity/history; granting rights does not claim settled payment.
- Member pricing uses declared catalog prices and immutable application/reversal facts; active package/member coverage cannot stack.
- Checkout wallets share a scoped mutation lease; one wallet cannot unlock payment while the other remains unconfirmed.
- Gift currency is explicitly configured and frozen after issuance; credited amount/code/expiry are replay-safe. Granting credit does not claim a sale.
- New walk-in/booking checkout tickets snapshot configured currency; legacy unknown invoices require explicit unpaid confirmation. Paid history cannot be relabeled; catalog additions/member tariffs cannot mix current and ticket currencies.
- Gift/mixed closure requires recorded allocations and currency-matched immutable closure facts; mixed remainder requires an explicit method. Historical paid-ticket replay is preserved (ADR-006).
- Active gift tenders freeze price/beneficiary changes and cancellation until reversed; credit corrections preserve expiry. Service revenue is unchanged, and cashier confirmation does not claim external settlement.
- Minimal customer identities support selection; legacy references are preserved. Full Phase 12 CRM lifecycle and public self-service are not claimed.
- Entitlement issuance does not claim a paid package sale or external payment settlement.
- Demo reset cannot erase commercial redemption-linked tickets.

BLOCKERS:
- Browser/tablet unavailable: last CUA inventory apps=[] and browsers=[]. Independent development continues.
- Deep load, external settlement and production readiness remain unverified.
- Currency-separated financial aggregation and cashier configuration/confirmation UI remain pending; legacy report totals do not establish comparable units.

NEXT_STEP:
- PHASE8M: manager currency/card issuance and cashier confirmation/lookup/debit/reversal/full-mixed payment UI with safe reconciliation; then loyalty and remaining canonical phases.
- Numbering follows detailed Master Plan sections 29-47 (Phase 8 Commerce, Phase 12 CRM); condensed Phase 8 Client 360 label is stale.
- Preserve open browser/tablet gates; do not infer production readiness from protocol/component checks.

LAST_COMMITS:
- Current: feat(gift-cards): record transactional tenders and full or mixed checkout.
- 348674f feat(checkout): preserve invoice currency and protect catalog pricing.
- 3b1fb52 feat(gift-cards): issue scoped credits with explicit currency and replay protection.
- 03c5ff1 feat(memberships): manage rights and reconcile member pricing in checkout.
- c3f3db6 feat(memberships): apply and reverse member pricing transactionally.
- 9424a92 feat(memberships): grant and renew scoped rights with immutable history.
- ca3a33a feat(commerce): configure and grant packages with replay-safe recovery.
- 817cb80 feat(checkout): identify anonymous customers safely before payment.
- e80c598 feat(commerce): apply and reverse packages from checkout.
- bca2049 feat(customers): select identities for arrivals and booking checkout.
- bc4f874 feat(commerce): reverse package consumption safely before payment.
- bf8dc72 feat(commerce): add scoped package balances and checkout consumption.
- b3d941d test(operations): verify live actions and recalculation across servers.
- 16d0fcc feat(booking): hand completed reservations to checkout transactionally.
- 3ff886c fix(operations): ignore action completions after institute changes.
- 42c6654 test(realtime): prove delivery across live server processes.

WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before the next unit.
