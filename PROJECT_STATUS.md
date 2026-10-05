CURRENT_PHASE = PHASE 9
CURRENT_CHECKPOINT = PHASE9C_DURABLE_OPERATION_REQUESTS
STATUS = ACTIVE

GATES:
- Historical Phase 0-3 closures preserved.
- Phase 4 functional scope PASS; browser/tablet remains open.
- PHASE5 = CLOSED: RESOURCE_SCHEDULING / SKILL_MATCHING / RESOURCE_CONFLICT = PASS.
- PHASE6 = CLOSED: HYBRID_BOOKING / BOOKING_CREATE / BOOKING_MOVE / BOOKING_CANCEL / RESOURCE_RESERVATION / COEXISTENCE_WALKIN_BOOKING = PASS.
- PHASE7 = PARTIAL: LIVE_BOARD / REALTIME_SYNC / LIVE_RECALCULATION PASS at authenticated two-process protocol scope; actual browser RECONNECT and TABLET_UX remain open.
- PHASE8 = PARTIAL: all four Commerce areas implemented at functional server/component scope; actual browser/tablet and external settlement remain open. Detailed requirement mapping: docs/architecture/COMMERCE_GATE_AUDIT.md.
- PHASE9 = IN_PROGRESS: typed PaymentProvider boundary/correlation and immutable scoped operation request persistence implemented; execution lifecycle, adapters, capture/refund and webhook processing pending. All Phase 9 gates remain open.
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Frontend: 53 tests and production build passed in JSDOM. Gift replay across remount, full/mixed intent, reversal, scoped recovery and late old-writer isolation verified; actual browser/tablet remains open.
- Gift manager/currency UI: explicit units, reason, same-intent recovery, token/context guards and uncertain-refresh payment latches verified. Bearer codes are not persisted or placed in URLs.
- Payment intent/migration PostgreSQL bundle: 4 passed; final intent checks: 2 passed, including duplicate creation and nonempty history guards on SQLite/PostgreSQL. Owned PostgreSQL upgrade/check passed.
- Payment provider boundary/correlation: 6 focused tests passed; amount, currency, status and stored-reference mismatches rejected; no live adapter, settlement or webhook lifecycle is claimed.
- Latest full backend: 250 passed, 51 opt-in PostgreSQL cases skipped locally. Final commercial-history PostgreSQL bundle: 4 passed (including the added opt-in union case). Redemption/migration PostgreSQL bundle: 14 passed, including duplicate spending/reversal and correction/spending races. Final enhanced checkout/history checks: 1 passed on SQLite and 1 on PostgreSQL. Earlier reward/migration and earning/migration bundles: 4 and 13 passed.
- Ticket commercial-history metadata: reversed package/member/loyalty line protection survives beneficiary changes and remount; 3 HTTP cases and 1 PostgreSQL union case passed. Single scoped SQL union adds no stored data or customer identity disclosure.
- Loyalty checkout recovery audit: foreign apply/reversal intents produce no POST; malformed reads retain payment latch; failed external reads hide stale eligibility; late old writer cannot refresh or release the newer ticket lease.
- Latest snapshot/redemption local check: 11 passed / 3 opt-in cases skipped. Snapshot PostgreSQL check: 2 passed, including concurrent correction consistency.
- Migrations through 2cef6714379c: SQLite/PostgreSQL round-trip/model parity, PostgreSQL upgrade/check and nonempty commercial-history downgrade guards passed; tier-only, point-ledger, earning-policy, earned-ticket, reward-term and redemption guards verified.
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
- Loyalty rewards debit points and reduce performed-line prices atomically; manager prepaid reversal credits the original cost and restores saved prices. Replays cannot undo newer coverage; active rewards block beneficiary changes/cancellation and history blocks line removal/reset.
- Entitlement issuance does not claim a paid package sale or external payment settlement.
- Demo reset cannot erase commercial redemption-linked tickets.

BLOCKERS:
- Browser/tablet unavailable: last CUA inventory apps=[] and browsers=[]. Independent development continues.
- Deep load, external settlement and production readiness remain unverified.
- Currency-separated financial aggregation remains pending; legacy report totals do not establish comparable units. Internal confirmation of a mixed remainder does not prove external card settlement.

NEXT_STEP:
- PHASE9D: validate quote/parent operation and seal execution before dispatch; persist/recover outcomes, then apply capture/refund/cancel/webhook transactionally with strict replay, unit and reference checks (Master Plan section 30).
- Numbering follows detailed Master Plan sections 29-47 (Phase 8 Commerce, Phase 12 CRM); condensed Phase 8 Client 360 label is stale.
- Preserve open browser/tablet gates; do not infer production readiness from protocol/component checks.

LAST_COMMITS:
- Current: feat(payments): persist immutable scoped operation requests.
- 82cf56b result correlation against original operation intent.
- 45d9252 typed provider contract and Commerce evidence audit.
- f043f7e ticket-wide commercial-history protection.
- 35fbd04 scoped loyalty recovery/eligibility audit.
- 23544bb checkout rewards and recovery.
- Earlier coherent Commerce checkpoints and evidence are retained in git log and ADR-007.
WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before the next unit.
