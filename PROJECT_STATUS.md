CURRENT_PHASE = PHASE 9
CURRENT_CHECKPOINT = PHASE9O_SIGNED_REFUND_LOYALTY_DECISIONS
STATUS = ACTIVE

GATES:
- Historical Phase 0-3 closures preserved.
- Phase 4 functional scope PASS; browser/tablet remains open.
- PHASE5 = CLOSED: RESOURCE_SCHEDULING / SKILL_MATCHING / RESOURCE_CONFLICT = PASS.
- PHASE6 = CLOSED: HYBRID_BOOKING / BOOKING_CREATE / BOOKING_MOVE / BOOKING_CANCEL / RESOURCE_RESERVATION / COEXISTENCE_WALKIN_BOOKING = PASS.
- PHASE7 = PARTIAL: LIVE_BOARD / REALTIME_SYNC / LIVE_RECALCULATION PASS at authenticated two-process protocol scope; actual browser RECONNECT and TABLET_UX remain open.
- PHASE8 = PARTIAL: all four Commerce areas implemented at functional server/component scope; actual browser/tablet and external settlement remain open. Detailed requirement mapping: docs/architecture/COMMERCE_GATE_AUDIT.md.
- PHASE9 = IN_PROGRESS: internal provider contracts, scoped intents/execution/outcomes, captured checkout, refund budgets and atomic webhook receipts implemented; manager-only cashflow read separates provider accounts/currencies. Signed manager refund loyalty decisions now link bounded deductions or explicit retention to confirmed refunds. Real authentication/transport, comprehensive accounting and operator mutation UI/recovery remain pending. All Phase 9 gates remain open.
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Signed refund loyalty decision/migration bundle: 4 passed / 2 opt-in skips locally and 6 passed with PostgreSQL enabled. Manager/JWT institute scope, strict bounded points, same-intent replay, one decision per refund, staged debit rollback, explicit retention, cumulative original-earning cap despite independent credits, actual PostgreSQL duplicate serialization and nonempty signed-history downgrade verified. Owned PostgreSQL upgrade/check passed. No automatic policy or negative balance inferred.
- Provider cashflow read: initial snapshot/refund local regression 5 passed / 1 opt-in skip. Currency/account separation checks: 2 passed locally; Linux cashflow/refund budget bundle 5 passed. Final cashflow suite 3 passed with the actual PostgreSQL fact-read case enabled. Scoped manager-only API, exact decimal string serialization, caller precision isolation, applied/unapplied capture distinction, confirmed/failed/unresolved refund handling and historical currency/account separation verified. No schema change.
- Webhook/provider/refund/migration bundle: 15 passed / 3 opt-in skips locally; PostgreSQL webhook/migration bundle: 7 passed. Final webhook/direct-outcome/captured-checkout regression: 19 passed / 5 opt-in skips locally; enhanced webhook PostgreSQL suite: 5 passed. Invalid test signature, missing/wrong correlation, all four operation routes, atomic receipt failure rollback, changed-event denial, concurrent delivery and nonempty receipt downgrade verified. Owned PostgreSQL upgrade/check passed. Test signature adapter is a simulation, not real provider authentication.
- Refund execution/budget/migration bundle: 6 passed / 3 opt-in skips locally and 9 passed on PostgreSQL. Final enhanced execution suite: 4 passed / 1 opt-in skip locally and 5 passed on PostgreSQL. Terminal no-I/O replay, unknown outcome recovery, failed-write reservation retention, verified-failure budget release, scope/value/reference/status rejection, concurrent duplicate refund and nonempty downgrade verified. Owned PostgreSQL upgrade/check passed. Simulated adapters do not establish real external settlement.
- Refund budget/parent/checkout regression: 9 passed / 3 opt-in skips locally and 12 passed on PostgreSQL. Final enhanced refund suite: 2 passed / 1 opt-in skip locally and 3 passed on PostgreSQL. Exact partial/remainder reservation, same-key replay at exhausted budget, changed-term denial, applied-capture/account/reference requirements, concurrent overdraw prevention and exclusion of gift-funded value verified. No new schema or refund dispatch at this checkpoint.
- Captured checkout/migration PostgreSQL bundle: 6 passed. Final checkout suite after explicit Decimal-context protection: 3 passed / 1 opt-in skip locally and 4 passed on PostgreSQL. Mixed gift/external remainder, duplicate paid application/one earning, failed earning rollback, immutable method replay and nonempty application downgrade guard verified. Owned PostgreSQL upgrade/check passed. No real adapter settlement is claimed.
- Capture/cancel execution, parent-proof and migration bundle: 14 passed / 3 opt-in skips locally and 17 passed on PostgreSQL. Final execution suite: 8 passed / 2 opt-in skips locally and 10 passed on PostgreSQL, including concurrent cancellation. Enhanced terminal-conflict/downgrade checks: 4 passed on each database. Owned PostgreSQL upgrade/check passed. Unknown transport, interrupted cancellation writes and seal rollback preserve parent protection; failed children allow another request; confirmed cancellation releases atomically. Captured checkout application is now implemented below at internal functional scope.
- Capture/cancel parent proof: intent/dispatch/outcome local regression bundle 13 passed / 5 opt-in skips; PostgreSQL parent/intent/outcome bundle 10 passed. Final parent suite: 5 passed / 1 opt-in skip locally and 6 passed on PostgreSQL. Confirmed full-value proof, same-account foreign-ticket denial, pending/failed denial, same-intent replay and competing capture/cancel reservation verified. Refund remains blocked until captured facts exist; no settlement or child dispatch claimed.
- Authorization dispatch/provider/outcome/seal/quote local bundle: 26 passed, 5 opt-in skips. PostgreSQL dispatch/outcome bundle: 11 passed. Final dispatch checks including invalid adapter responses: 6 passed / 2 opt-in skips locally and 8 passed on PostgreSQL. Original request recovery, terminal no-I/O replay, failed-write latch, account mismatch, concurrent idempotent retries and no institute lock during network callback verified with simulated adapters.
- Authorization outcomes/provider/seal/quote/migration local bundle: 22 passed, 4 opt-in skips. PostgreSQL outcomes/migration bundle: 6 passed. Final outcomes suite including the added prior-execution check: 4 passed / 1 opt-in skip locally and 5 passed on PostgreSQL. Owned PostgreSQL upgrade/check passed. Scope/reference/value mismatches, duplicate terminal observations, terminal conflicts and failed-write rollback covered.
- Authorization execution seals: final focused local checks 3 passed / 2 opt-in cases skipped; final PostgreSQL seal/intent bundle 7 passed. Competing authorizations and price mutation/seal races verified. Migration bundle 6 passed, including SQLite/PostgreSQL round-trip/model parity and nonempty execution guards; owned PostgreSQL upgrade/check passed.
- Authorization quote/provider/intent checks: 16 passed, 1 opt-in case skipped locally; PostgreSQL quote/intent bundle: 11 passed. Gift remainder, quote drift, ineligible tickets and missing/inconsistent prices rejected; original persisted replay preserved.
- Frontend: 53 tests and production build passed in JSDOM. Gift replay across remount, full/mixed intent, reversal, scoped recovery and late old-writer isolation verified; actual browser/tablet remains open.
- Gift manager/currency UI: explicit units, reason, same-intent recovery, token/context guards and uncertain-refresh payment latches verified. Bearer codes are not persisted or placed in URLs.
- Payment intent/migration PostgreSQL bundle: 4 passed; final intent checks: 2 passed, including duplicate creation and nonempty history guards on SQLite/PostgreSQL. Owned PostgreSQL upgrade/check passed.
- Payment provider boundary/correlation: 6 focused tests passed; amount, currency, status and stored-reference mismatches rejected; no live adapter, settlement or webhook lifecycle is claimed.
- Latest full backend: 288 passed, 60 opt-in PostgreSQL cases skipped locally; final Decimal-context enhancement subsequently passed in the focused checkout suite on SQLite/PostgreSQL. Final commercial-history PostgreSQL bundle: 4 passed (including the added opt-in union case). Redemption/migration PostgreSQL bundle: 14 passed, including duplicate spending/reversal and correction/spending races. Final enhanced checkout/history checks: 1 passed on SQLite and 1 on PostgreSQL. Earlier reward/migration and earning/migration bundles: 4 and 13 passed.
- Ticket commercial-history metadata: reversed package/member/loyalty line protection survives beneficiary changes and remount; 3 HTTP cases and 1 PostgreSQL union case passed. Single scoped SQL union adds no stored data or customer identity disclosure.
- Loyalty checkout recovery audit: foreign apply/reversal intents produce no POST; malformed reads retain payment latch; failed external reads hide stale eligibility; late old writer cannot refresh or release the newer ticket lease.
- Latest snapshot/redemption local check: 11 passed / 3 opt-in cases skipped. Snapshot PostgreSQL check: 2 passed, including concurrent correction consistency.
- Migrations through 93f0348baef2: SQLite/PostgreSQL round-trip/model parity, PostgreSQL upgrade/check and nonempty commercial-history downgrade guards passed; tier-only, point-ledger, earning-policy, earned-ticket, reward-term and redemption guards verified.
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
- Demo reset cannot erase commercial redemption-linked tickets or durable payment requests.
- Active authorization executions freeze ticket mutations, commercial price changes and new gift funding/reversal; original intent recovery never re-quotes an unknown provider outcome. Pending/authorized outcomes retain the seal; explicit final failure releases it atomically with its immutable fact. Child cancellation releases the parent with its confirmed fact; captured funds remain protected until checkout application. Failed child requests allow a new operation while keeping history. No timeout-based release or external settlement is inferred.

BLOCKERS:
- Browser/tablet unavailable: last CUA inventory apps=[] and browsers=[]. Independent development continues.
- Deep load, external settlement and production readiness remain unverified.
- Provider cashflow read now separates accounts/currencies; legacy service report totals still do not establish comparable units. Full net sales, bank payouts, fees/taxes and automated refund policy and full accounting remain pending; explicit signed refund loyalty decisions are now available. Internal cashier confirmation does not prove external settlement.

NEXT_STEP:
- PHASE9P: integrate payment operation/read/recovery UI and real authenticated adapter/transport; complete accounting consequences and broader verification before closing payment gates; persist/recover outcomes, then apply capture/refund/cancel/webhook transactionally with strict replay, unit and reference checks (Master Plan section 30).
- Numbering follows detailed Master Plan sections 29-47 (Phase 8 Commerce, Phase 12 CRM); condensed Phase 8 Client 360 label is stale.
- Preserve open browser/tablet gates; do not infer production readiness from protocol/component checks.

LAST_COMMITS:
- Current: feat(payments): link signed loyalty decisions to confirmed refunds.
- ef428fe scoped provider cashflow read.
- 730c4a6 atomic correlated webhook receipts.
- 4b813d9 durable refund dispatch and outcomes.
- d3f1b4a captured-amount refund reservations.
- ec9f9ee atomic captured checkout application.
- 0e9ed73 durable capture/cancel execution and provider facts.
- c082209 capture/cancel parent proof and reservations.
- 6a391ca trusted account-bound authorization dispatch.
- e82a70f immutable authorization observations.
- 78b0055 durable authorization execution seals.
- 2310d22 exact authorization quote validation.
- d435c34 immutable scoped operation requests.
- 82cf56b result correlation against original operation intent.
- 45d9252 typed provider contract and Commerce evidence audit.
- f043f7e ticket-wide commercial-history protection.
- 35fbd04 scoped loyalty recovery/eligibility audit.
- 23544bb checkout rewards and recovery.
- Earlier coherent Commerce checkpoints and evidence are retained in git log and ADR-007.
WORKING_TREE:
- Checkpoint reviewed and committed; inspect git status before the next unit.
