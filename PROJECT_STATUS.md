CURRENT_PHASE = PHASE 9
CURRENT_CHECKPOINT = PHASE9AB_DECIMAL_CHIFFRES_API
STATUS = ACTIVE

RECOVERY_READ:
- Manager-only refund decision GET returns the immutable original idempotency key; absence is null and missing/foreign refund intents return scoped 404.
- Shared payment-route dependencies enforce institute, exact signed actor and manager privileges consistently. No point mutation, provider dispatch or schema change.
- Focused local refund/snapshot/cashflow checks: 7 passed, 3 opt-in skips. PostgreSQL refund/snapshot checks: 7 passed, including concurrent decisions and recovery identity/role boundaries.
- Full backend regression: 305 passed, 66 opt-in PostgreSQL skips. Payment history component compatibility checks: 2 passed; no frontend source change.

GATES:
- Historical Phase 0-3 closures preserved.
- Phase 4 functional scope PASS; browser/tablet remains open.
- PHASE5 = CLOSED: RESOURCE_SCHEDULING / SKILL_MATCHING / RESOURCE_CONFLICT = PASS.
- PHASE6 = CLOSED: HYBRID_BOOKING / BOOKING_CREATE / BOOKING_MOVE / BOOKING_CANCEL / RESOURCE_RESERVATION / COEXISTENCE_WALKIN_BOOKING = PASS.
- PHASE7 = PARTIAL: LIVE_BOARD / REALTIME_SYNC / LIVE_RECALCULATION PASS at authenticated two-process protocol scope; actual browser RECONNECT and TABLET_UX remain open.
- PHASE8 = PARTIAL: all four Commerce areas implemented at functional server/component scope; actual browser/tablet and external settlement remain open. Detailed requirement mapping: docs/architecture/COMMERCE_GATE_AUDIT.md.
- PHASE9 = IN_PROGRESS: internal provider contracts, scoped intents/execution/outcomes, captured checkout, refund budgets and atomic webhook receipts implemented; manager-only cashflow read separates provider accounts/currencies. Signed manager refund loyalty decisions now link bounded deductions or explicit retention to confirmed refunds. Real authentication/transport and comprehensive accounting remain pending; manager refund loyalty mutation/recovery UI is implemented at component scope; ticket payment recovery read and checkout history UI now expose scoped original operations and signed decisions. All Phase 9 gates remain open.
- PRODUCTION_READY = NOT_VERIFIED.

EVIDENCE:
- Chiffres monetary DTO fields now remain Decimal and serialize as two-decimal strings; the UI formats recorded digits directly without JavaScript Number conversion. API/UI regression preserves 90071992547409.93 cents exactly. Final local report/checkout bundle: 11 passed, 1 opt-in skip. Frontend: 79 passed and production build passed. Nullable unknown/mixed totals and original-currency groups remain unchanged. No migration or bank settlement claim.
- Final report serialization/PostgreSQL/two-process HTTP-WebSocket bundle: 6 passed. Prior full backend baseline remains 319 passed / 67 opt-in skips; no new full-suite claim for this focused serialization correction. Browser/tablet remains open.
- Chiffres now groups original paid-ticket currency, uses Decimal accumulation under precision 28, shares one source ticket set/period, and returns null legacy monetary totals for mixed/unknown units. Unknown historical tickets are counted without monetary aggregation. UI selects labelled CHF/EUR groups and hides unlabelled totals. Focused report/checkout tests: 10 passed, 1 opt-in skip locally; report suite: 3 passed with actual PostgreSQL enabled. Frontend: 78 passed and build passed. ADR-009 records contract/nullability and scope.
- Full backend regression after report contract change: 319 passed, 67 opt-in skips. Final report component checks after initial-loading wording guard: 2 passed and build passed. No migration or production/tablet claim.
- Final two-process PostgreSQL HTTP/WebSocket protocol: 2 passed after explicit institute/invoice currency setup. Currency confirmation is a REST commercial mutation, not a planning-event notification; the fixture preserves actual planning event assertions. Actual browser/tablet verification remains open.
- Full operator HTTP scenario now verifies declared earning policy, authorization, capture, unapplied/applied cashflow, atomic checkout replay, reserved/confirmed partial refund, signed manager loyalty decision replay/recovery, linked ticket snapshot and final customer balance. 10.35 CHF captured, 5.00 CHF refunded, 5.35 CHF confirmed net; one capture application and exactly +10/-5 point entries. Cross-module bundle: 19 passed, 3 opt-in skips locally; 22 passed with PostgreSQL enabled (HTTP fixtures SQLite, opted-in domain cases actual PostgreSQL). Explicit simulated adapter only; no browser or bank settlement claim.
- Obsolete prepared authorization UI blockage fixed: prepared-only history no longer hides the current server quote/new authorization control. Unknown/pending outcomes or active protection still hide it. A new explicit key may prepare the current quote while preserving the old immutable request. HTTP regression proves old changed-price dispatch is rejected before adapter I/O, current request dispatch succeeds once, old retry cannot acquire a competing execution, and both original histories remain. Frontend regression: 76 passed plus build.
- Final operator/quote/execution regression: 24 passed, 2 opt-in PostgreSQL skips locally; 26 passed with PostgreSQL enabled (HTTP fixtures SQLite, opted-in execution cases actual PostgreSQL). Initial Windows SQLite teardown file-lock error was followed by a passing isolated rerun and clean full focused-bundle rerun; no fixture change or suppressed cleanup error.
- Initial authorization: scoped/configuration-required GET reads exact current amount/currency under the institute lock without creating an intent or provider I/O. Eligible checkout history exposes quote/preparation only after a clean scoped snapshot without protected/unknown/pending operations. Frozen original authorization terms/key survive lost replies; later quote changes do not rewrite a saved request. Frontend: 75 passing tests plus build; final preparation suite after label correction: 7 passed plus build. Backend operator/quote/intent bundle: 21 passed, 1 opt-in skip locally; 22 passed with PostgreSQL enabled (HTTP fixtures SQLite, opted-in domain fixture actual PostgreSQL). No schema or real adapter added.
- Parent payment preparation UI: 5 new focused cases within 73 passing frontend tests; production build passed. Active authorized operations expose capture/cancel preparation; applied confirmed captures expose manager-only refund preparation with explicit currency/amount. Original terms/key are stored before POST and recovered across remount, then original actor/key/value are checked in a scoped snapshot before refresh. Lost reply replay and changed-response value rejection verified. Server still owns parent references, authorization proof, role checks and reserved refund budget. Initial authorization UI and real provider remain pending.
- Captured checkout UI: 3 new focused cases within 68 passing frontend tests; production build passed. Only original actors may apply a confirmed unapplied capture with explicit cashier/method. Original closure terms are saved before POST and replayed across remount despite changed selections. Paid response and matching applied capture snapshot are required before full data refresh/intent clearing. Lost replies, unapplied facts, failed refresh and late-session isolation verified. No new capture/provider dispatch is inferred.
- Checkout payment recovery UI: 3 new focused cases within 65 passing frontend tests; production build passed. Prepared/unknown/pending operation recovery uses the durable original ID and no request body/new intent. Response and scoped stored fact must match original kind/value/currency/actor before application refresh. Original-actor and refund-manager presentation guards, lost response retry, wrong snapshot scope and late-session isolation verified. Initial authorization/child preparation and captured checkout controls remain to implement; no live provider or browser/tablet verification claimed.
- Adapter HTTP exceptions are now normalized inside the provider-call boundary, separately from FlowPilot preflight/domain HTTP errors. They retain unknown execution/refund reservations and return generic recovery responses, never a false definitive rejection. Webhook adapter HTTP exceptions cannot acknowledge or write a receipt. Five new cases verify all four operations and callback recovery, including exclusion of private provider details/headers.
- Final HTTP-error/dispatch/refund/webhook regression: 24 passed, 4 opt-in PostgreSQL skips locally; 28 passed with PostgreSQL enabled (HTTP fixtures SQLite, opted-in domain cases actual PostgreSQL). Prior full backend baseline: 310 passed, 66 opt-in skips; no new full-suite claim for this focused correction.
- Operator payment HTTP routes now prepare immutable requests, dispatch original signed intents, apply confirmed captures and receive authenticated raw webhooks. Empty server binding configuration refuses with 503; no fake/default provider. Parent references/accounts are resolved server-side. Unknown transport preserves durable protection and original-key recovery. Endpoint tests use an explicit simulated adapter; real provider integration and operator dispatch UI remain open.
- Payment operator API: 5 final local cases passed; operator/dispatch/checkout/refund/webhook bundle with PostgreSQL enabled: 27 passed (HTTP fixtures remain SQLite; opted-in domain cases use actual PostgreSQL). Full backend: 310 passed, 66 opt-in skips. No schema change or real external settlement. API contract: docs/architecture/PAYMENT_OPERATOR_API.md.
- Signed refund decision UI: 7 focused cases within 62 passing frontend tests; production build passed. Explicit zero retention/negative deduction, intent persistence before POST, lost-response recovery without another POST, exact receipt-key matching, refresh-failure latch, late-session isolation, cashier read-only/confirmed-refund gating and definitive rejection correction verified. Fresh CUA apps=[] and browsers=[]; actual browser/tablet remains open.
- Checkout payment history component: 2 focused tests passed within the 55-test frontend suite; production build passed. Protected unknown result display, wrong-ticket read rejection/stale clearing and late old ticket/token isolation verified. Read-only refresh releases no mutation lease. Fresh CUA inventory apps=[] and browsers=[]; visual/tablet gates remain open.
- Ticket payment recovery snapshot/refund-decision/cashflow regression: 7 passed / 3 opt-in skips locally. Final snapshot suite with PostgreSQL enabled: 3 passed, including an actual PostgreSQL transition read. Prepared/unknown/pending/terminal distinctions, live protection, capture application, linked decision recovery, exact monetary serialization, JWT/ticket scope rejection and exclusion of provider references verified. No schema change.
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
- Frontend: 79 tests and production build passed in JSDOM. Gift replay across remount, full/mixed intent, reversal, scoped recovery and late old-writer isolation verified; actual browser/tablet remains open.
- Gift manager/currency UI: explicit units, reason, same-intent recovery, token/context guards and uncertain-refresh payment latches verified. Bearer codes are not persisted or placed in URLs.
- Payment intent/migration PostgreSQL bundle: 4 passed; final intent checks: 2 passed, including duplicate creation and nonempty history guards on SQLite/PostgreSQL. Owned PostgreSQL upgrade/check passed.
- Payment provider boundary/correlation: 6 focused tests passed; amount, currency, status and stored-reference mismatches rejected; no live adapter, settlement or webhook lifecycle is claimed.
- Latest full backend: 319 passed, 67 opt-in PostgreSQL cases skipped locally; final Decimal-context enhancement subsequently passed in the focused checkout suite on SQLite/PostgreSQL. Final commercial-history PostgreSQL bundle: 4 passed (including the added opt-in union case). Redemption/migration PostgreSQL bundle: 14 passed, including duplicate spending/reversal and correction/spending races. Final enhanced checkout/history checks: 1 passed on SQLite and 1 on PostgreSQL. Earlier reward/migration and earning/migration bundles: 4 and 13 passed.
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
- Provider cashflow separates accounts/currencies; Chiffres now separates original invoice currencies and suppresses unknown/mixed monetary totals. Full net sales, bank payouts, fees/taxes and automated refund policy and full accounting remain pending; explicit signed refund loyalty decisions are now available. Internal cashier confirmation does not prove external settlement.

NEXT_STEP:
- PAYMENT_ACCOUNTING_INTEGRATION: continue real adapter, integration and accounting verification; complete broader accounting/integration verification before closing payment gates; persist/recover outcomes, then apply capture/refund/cancel/webhook transactionally with strict replay, unit and reference checks (Master Plan section 30).
- Numbering follows detailed Master Plan sections 29-47 (Phase 8 Commerce, Phase 12 CRM); condensed Phase 8 Client 360 label is stale.
- Preserve open browser/tablet gates; do not infer production readiness from protocol/component checks.

LAST_COMMITS:
- Current: fix(reporting): preserve exact decimal amounts through Chiffres API and UI.
- b650956 original invoice currency reporting.
- e733262 HTTP cashflow and refund loyalty integration audit.
- 28866e3 obsolete prepared authorization recovery guard.
- 3b7f955 initial authorization from exact server quote UI.
- ed308ed child payment preparation UI.
- 2860784 captured checkout application UI.
- 6aafca1 original payment operation recovery UI.
- 9cbeae0 adapter HTTP uncertainty and recovery guards.
- 18e6f13 scoped operator payment orchestration API.
- 46012b2 signed refund loyalty mutation/recovery UI.
- be53cbd scoped signed refund decision recovery read.
- 9a7fea9 checkout payment history read UI.
- 0841b38 ticket payment recovery snapshot.
- 6215820 signed refund loyalty decisions.
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
