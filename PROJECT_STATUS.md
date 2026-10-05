CURRENT_PHASE = PHASE 8
CURRENT_CHECKPOINT = PHASE8S_EXPLICIT_REWARD_TERMS
STATUS = ACTIVE

GATES:
- Historical Phase 0-3 closures preserved.
- Phase 4 functional scope PASS; browser/tablet remains open.
- PHASE5 = CLOSED: RESOURCE_SCHEDULING / SKILL_MATCHING / RESOURCE_CONFLICT = PASS.
- PHASE6 = CLOSED: HYBRID_BOOKING / BOOKING_CREATE / BOOKING_MOVE / BOOKING_CANCEL / RESOURCE_RESERVATION / COEXISTENCE_WALKIN_BOOKING = PASS.
- PHASE7 = PARTIAL: LIVE_BOARD / REALTIME_SYNC / LIVE_RECALCULATION PASS at authenticated two-process protocol scope; actual browser RECONNECT and TABLET_UX remain open.
- PHASE8 = IN_PROGRESS: PACKAGES / MEMBERSHIPS functional server/component scope PASS. GIFTCARDS scoped issuance/tenders implemented at server/component scope; browser/tablet and external settlement remain open. LOYALTY = IN_PROGRESS: manual point ledger, explicit tiers and transactional checkout earning API implemented; explicit immutable reward terms configured; reward application/reversal and UI remain.
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Frontend: 44 tests and production build passed in JSDOM. Gift replay across remount, full/mixed intent, reversal, scoped recovery and late old-writer isolation verified; actual browser/tablet remains open.
- Gift manager/currency UI: explicit units, reason, same-intent recovery, token/context guards and uncertain-refresh payment latches verified. Bearer codes are not persisted or placed in URLs.
- Latest full backend: 229 passed, 45 opt-in PostgreSQL cases skipped locally. Final reward check after race-test extension: 1 passed / 1 skipped. Reward/migration PostgreSQL bundle: 4 passed, including duplicate creation and currency races. Earlier earning/migration bundle: 13 passed.
- Migrations through 0acd45f2157a: SQLite/PostgreSQL round-trip/model parity, PostgreSQL upgrade/check and nonempty commercial-history downgrade guards passed; tier-only, point-ledger, earning-policy, earned-ticket and reward-term guards verified.
- Phase 7 live two-process PostgreSQL suite: 2 passed with action revisions followed by reader-side REST verification. This does not establish actual browser reconnect/tablet UX.
- Earlier package/membership/booking/resource evidence and scope are retained in git history and docs/architecture/COMMERCE.md, HYBRID_BOOKING.md, RESOURCES_AND_SKILLS.md and REALTIME_OPERATIONS.md.
INVARIANTS:
- Deterministic institute-scoped business truth; BASE/JV separation preserved.
- Booking/resource/history/checkout handoff is transactional; legacy finished bookings are not rebilled.
- Package balance, price coverage and immutable redemption history share one transaction and institute lock.
- Checkout customer correction uses the same lock; active coverage and paid states prevent beneficiary changes.
- Membership grant/renewal uses registered scoped identities, snapshotted terms and transactional validity/history; granting rights does not claim settled payment.
- Member pricing uses declared catalog prices and immutable application/reversal facts; active package/member coverage cannot stack.
- Checkout wallets share a scoped mutation lease; one wallet cannot unlock payment while the other remains unconfirmed.
- Gift currency is explicitly configured and frozen after issuance, loyalty policy or reward creation; credited amount/code/expiry are replay-safe. Granting credit does not claim a sale.
- New walk-in/booking checkout tickets snapshot configured currency; legacy unknown invoices require explicit unpaid confirmation. Paid history cannot be relabeled; catalog additions/member tariffs cannot mix current and ticket currencies.
- Gift/mixed closure requires recorded allocations and currency-matched immutable closure facts; mixed remainder requires an explicit method. Historical paid-ticket replay is preserved (ADR-006).
- Active gift tenders freeze price/beneficiary changes and cancellation until reversed; credit corrections preserve expiry. Service revenue is unchanged, and cashier confirmation does not claim external settlement.
- Minimal customer identities support selection; legacy references are preserved. Full Phase 12 CRM lifecycle and public self-service are not claimed.
- Loyalty balance derives from scoped immutable history; manager corrections are not automatic purchase earnings. Paid checkout awards points once from actual line totals using an explicit immutable rate/currency revision, rounded down to whole points; zero earnings are recorded. Failed earning writes roll back closure. Tier descriptions do not apply unconfigured discounts or infer loyalty from membership.
- Entitlement issuance does not claim a paid package sale or external payment settlement.
- Demo reset cannot erase commercial redemption-linked tickets.

BLOCKERS:
- Browser/tablet unavailable: last CUA inventory apps=[] and browsers=[]. Independent development continues.
- Deep load, external settlement and production readiness remain unverified.
- Currency-separated financial aggregation remains pending; legacy report totals do not establish comparable units. Internal confirmation of a mixed remainder does not prove external card settlement.

NEXT_STEP:
- PHASE8S: actual loyalty reward application/reversal and UI (Master Plan section 29); preserve provider settlement for canonical payment/sales phases.
- Numbering follows detailed Master Plan sections 29-47 (Phase 8 Commerce, Phase 12 CRM); condensed Phase 8 Client 360 label is stale.
- Preserve open browser/tablet gates; do not infer production readiness from protocol/component checks.

LAST_COMMITS:
- Current: feat(loyalty): configure explicit immutable service rewards.
- a5926d0 transactional earning with immutable policy and checkout facts.
- e7dee67 scoped points and explicit balance tiers.
- c690feb gift recovery scope/history audit.
- aae1138 gift tender wallet and full/mixed checkout.
- 2f92211 cashier currency confirmation.
- 62a6b4e manager gift configuration/issuance recovery.
- 31cd388 transactional gift tenders and closure facts.
- 348674f invoice currency snapshots and price protection.
- Earlier coherent checkpoints are retained in git log.
WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before the next unit.
