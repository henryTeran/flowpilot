# ADR-008: Scoped payment-provider boundary

Status: Accepted for interface and value validation; payment lifecycle pending.
Date: 2026-10-06

Master Plan section 30 requires authorize, capture, refund, cancel and webhook,
with mandatory idempotence. The modular monolith keeps adapter I/O in the payments
domain, separate from deterministic planning and checkout business truth.

`PaymentProvider` declares all five operations. Requests include institute, ticket,
signed actor and replay key with bounded identifiers. Amounts are positive finite
Decimal values in explicit CHF/EUR, with whole cents and no implicit float or
exchange conversion. Canonicalization does not inherit caller Decimal precision.
Results carry typed status, value and provider reference, never a guessed payment
outcome. A timeout remains unknown and must reuse the original persisted intent.

Webhook input retains raw bytes and immutable copied headers without displaying
body/headers in repr. An adapter must authenticate its configured account before
emitting VerifiedWebhook. Public endpoints must not accept a verified flag or this
internal output type. Tenant/ticket must be resolved from stored provider references.

This checkpoint supplies no live adapter, default provider, capture, refund or
webhook endpoint. Result validation now rejects changed amount/currency, mismatched stored
reference, missing reference for capture/refund/cancel and a status from another
operation. Pending/failed are observations and never imply settlement. Stored
account/tenant lookup and authentication still remain domain responsibilities.
Durable operations, transactional application, replay/concurrency and real integration
verification remain required. Existing cashier closure is an internal confirmation;
it cannot establish external settlement. All Phase 9 gates remain open.

Focused tests check decimal units, precision, immutable intent, typed results,
bounded identifiers, raw input validation and copied secret-bearing headers.


Immutable PaymentIntent records now persist provider/account alias, ticket/institute,
operation, original decimal amount/currency, provider reference, signed actor and
replay key before adapter I/O. The institute lock and scoped unique key serialize
creation. Changed terms (including original actor) fail; identical replay returns
the stored request even if the ticket quote changes later. Unknown/mismatched
institute ticket and unconfirmed currency cannot create a request. Account aliases
are identifiers, never credentials. Any intent protects its linked ticket from demo
reset and a nonempty downgrade refuses before DDL.

Persistence is not authorization to dispatch: parent-operation checks,
sealing business changes during I/O, execution state, authenticated provider facts,
refund budgets and transactionally applying capture to checkout remain pending.
No public endpoint or live provider call is added at this checkpoint.


New authorizations now require an unpaid checkout ticket, an explicit supported
currency, consistent declared line prices and a positive exact remaining amount
after gift funding. The requested value must equal this quote. Identical persisted
replay still returns its original terms before consulting later ticket changes.
A first-dispatch validator recomputes the quote under the institute transaction
lock and rejects drift. The caller must seal execution before releasing that lock;
this helper performs no I/O and is not an execution record. Recovery after an
unknown outcome must use the original sealed request rather than re-quote.
Parent-operation proof, execution sealing, business mutation protection, provider
facts and settlement remain pending. All Phase 9 gates remain open.


Authorization execution now has a durable seal separate from the immutable
request. Under the institute lock, first execution rechecks the current quote,
rejects a competing active execution, inserts the seal and commits before returning
the original request for future adapter I/O. One partial unique index additionally
limits active seals to one per ticket. Retry returns the original request without
re-quoting; it never interprets a timeout as failure or releases the seal.

Ticket mutation locks, package/member/loyalty price guards and new gift allocation
or reversal reject active executions. Existing allocation/coverage replays remain
read-only and preserve their original facts. There is deliberately no release API,
public dispatch endpoint or external call yet: authenticated provider outcomes,
terminal release and checkout application must be implemented together. The
execution ledger has a nonempty downgrade guard. This is authorization sealing,
not capture/refund/cancel parent-operation validation or completed settlement.


Authorization observations now persist as immutable pending/authorized/failed
facts linked to a prior durable execution. This internal writer checks the trusted
adapter provider/account binding, original amount/currency and operation kind.
The first result binds the provider reference; a global provider/account/reference
key prevents assigning the same external operation to a different intent. The
institute lock serializes duplicate observations and terminal transitions.

Matching observation replay returns its existing fact. A terminal observation
cannot be replaced, and a new pending observation cannot regress a terminal state.
Previously recorded pending facts remain readable by matching replay. Pending and
authorized retain the execution seal; explicit final failed releases it in the same
transaction as the outcome. Failed persistence leaves both facts and release absent.
Timeouts are not observations and provide no release path. A successful authorization
is not capture or settled revenue. No public route accepts these internal facts;
the configured adapter driver and authentication must precede any production use.
Nonempty outcome/reference downgrade refuses before DDL. Real adapters, dispatch
recovery, capture/cancel/refund parent proofs and webhook lifecycle remain pending.


The internal authorization dispatcher now selects an explicit institute/provider/
account binding and owns short-lived SQL sessions. It validates the stored binding,
seals execution durably, returns any existing terminal fact without network I/O,
and closes its session before calling the adapter. Recording the authenticated
adapter result uses a new transaction and the existing outcome validator. Unknown
transport or persistence failures keep the seal and original request recoverable.
Pending retries use the original provider key and amount without a fresh quote.
Concurrent retries require provider-side idempotence; the domain serializes outcome
writes but deliberately holds no institute lock across external I/O. PostgreSQL
checks demonstrate the institute row is lockable during the adapter callback.

ProviderBinding is server configuration, not a request schema, and hides its adapter
from repr. No default/live provider or public payment endpoint is introduced. Test
adapters establish orchestration and recovery, not authentication or settlement for
an external account. Capture/cancel/refund proofs, their dispatch and checkout
application, real adapter integration and webhook replay remain required.


New capture/cancel requests now resolve their parent using the stored provider/
account/reference binding. Parent authorization, institute, ticket, confirmed
observation, active protection, amount and currency must match. This first
implementation supports full authorization capture/cancel; partial/multiple capture
is not configured. Preparation reserves the parent by persisting one capture or
cancel request under the institute lock, preventing competing opposite requests.
Original same-key replay still returns before consulting later parent state.
Unresolved prepared requests are not abandoned or released implicitly; their durable
execution/result recovery must follow. Refund preparation requires captured facts
and is rejected until that ledger exists. No capture/cancel dispatch, settlement,
parent release or checkout application is claimed by these prerequisite checks.


Capture/cancel now have their own durable execution seals and immutable observation
ledger. The seal snapshots the parent link after validating the original request;
recovery reuses original terms before reconsidering parent state. The account-bound
dispatcher closes its SQL session before calling capture/cancel and returns stored
terminal observations without new provider I/O. Exact request value, status and
stored reference validation precede every outcome write.

Pending/unknown retains parent protection. Confirmed cancellation releases the
parent in the same transaction as its immutable fact. Confirmed capture retains
protection until captured settlement is applied to checkout, preventing an unrelated
cashier closure or new charge in the interim. Explicit child failure leaves the
parent authorization active and allows another capture/cancel request; historical
failed requests and seals remain immutable. Terminal conflicts cannot rewrite facts.
Interrupted persistence cannot release the parent. The new migration refuses to
downgrade nonempty execution or outcome history before dropping any table.

These internal adapter simulation checks do not establish external integration or
production settlement. Refund budgets and execution,
webhook authentication/replay, real providers and operator UI remain required.


Confirmed capture now applies to checkout through an explicit signed original actor,
institute, capture intent, cashier employee and tender method. Its immutable ticket/
capture application fact is unique. Existing matching application replay returns
before consulting later quote/policy state; changed employee/actor/method cannot
relabel paid history. New application requires the protected parent and exact current
remaining amount in the captured currency. Gift-funded checkout uses the declared
external method for the mixed remainder and preserves existing gift allocation facts.

The application fact, parent release, normal paid transition, gift closure and loyalty
award share the existing checkout transaction. Checkout runs in an explicit Decimal
precision context so gift remainder and earning calculations do not inherit caller
precision. Release is flushed while retaining the
institute lock before invoking checkout; failed checkout/earning writes roll back the
application and release. Concurrent duplicate application returns one paid ticket and
one loyalty award. Nonempty downgrade refuses before dropping the application table.
No public endpoint or real provider integration is claimed by this internal writer.
Refund budgets/execution, webhook authentication/replay, actual adapters and operator
UI remain open; all Phase 9 production gates remain open.


New refund requests now require a scoped provider/account/reference capture with a
confirmed captured outcome and its matching checkout application. Authorization,
invoice totals and gift allocations cannot supply external refund capacity. Within
the institute lock, the capture amount minus all existing refund request amounts is
the available reservation budget; partial requests use exact cents and the same
explicit currency. Every unresolved reservation counts, including requests that
have not yet dispatched. Timeout or abandonment cannot silently restore capacity.
Original identical replay is resolved before budget validation and does not reserve
money twice; changed replay terms still fail. Decimal arithmetic uses local precision.

This checkpoint prepares immutable refund requests only. There is no refund dispatch
or outgoing settlement fact yet, and no implicit release of failed reservations.
Verified refund failure release, execution recovery, accounting/loyalty consequences,
real adapters and webhook processing remain required. Paid service history is unchanged.


Refund execution now seals the immutable request against its captured parent before
external I/O. First sealing excludes only its validated matching reservation from
budget revalidation; recovery preserves the original request without re-reserving.
The account-bound dispatcher closes its SQL session before calling refund and returns
existing terminal observations without another provider call. Immutable pending/
refunded/failed outcomes require the durable seal, exact amount/currency, original
reference and configured provider/account. Terminal outcomes cannot be replaced.

Only a persisted explicit failed outcome makes its reservation available again;
unknown transport or interrupted persistence retains capacity. Successful refunds
continue consuming the captured budget. Original requests/seals/facts are retained.
No paid service or loyalty history is rewritten automatically: refund accounting,
loyalty adjustment policy and operator workflow require explicit implementation.
SQLite/PostgreSQL nonempty history guards refuse downgrade before DDL. Test adapters
prove recovery/concurrency only; real integration and authenticated webhook handling
remain open, and no public payment endpoint is introduced.


The internal webhook receiver passes raw bytes/headers to the server-selected
account adapter before opening SQL. VerifiedWebhook now supports an explicit original
operation key; missing correlation is refused rather than guessing from reference,
amount or status. The institute/provider/account/key must resolve a stored request.
Capture, cancellation and refund must also match their stored provider reference.
Only configured adapters may authenticate and construct these internal events.

Each provider/account/event ID has one immutable semantic receipt (intent, status,
reference and decimal value). Matching redelivery returns the original result;
changed semantic content is refused. Outcome writers expose an internal flush-only
mode so the business fact, any release and receipt commit in one transaction. Receipt
failure rolls back the outcome/release; concurrent duplicates serialize under the
institute lock with global account/event uniqueness as an additional guard. Raw bodies
and secret-bearing headers are neither saved in the receipt nor displayed by repr.
Nonempty delivery history prevents downgrade before DDL.

Simulation verifies orchestration and replay across all four operation kinds, not
actual provider signature validation. Real authenticated adapters, public transport
configuration, operator workflow and refund accounting/loyalty consequences remain
open. All Phase 9 gates remain open pending that broader integration verification.


A manager-only institute cashflow snapshot now reads confirmed provider facts under
the institute lock. It reports separate provider/account/currency groups with captured,
applied, unapplied, confirmed refunded, unresolved refund reservations and confirmed
net amounts. Exact Decimal arithmetic preserves cents independently of caller context;
API monetary values are decimal strings. Authorizations, cancellation, failed refunds,
gift credit and ordinary internal cashier confirmations are not incoming/outgoing
settlement facts. No cross-unit or cross-account grand total is invented.

This is a provider cashflow view, not service revenue, bank payout reconciliation,
fees, taxes or a general ledger. Read-only reporting neither reverses performed work
nor chooses a loyalty refund policy. Actual provider verification and full accounting/
operator integration remain open. No schema change is required for this snapshot.


Confirmed refunds now support one explicit, signed manager loyalty decision. Zero
records a reasoned decision to retain points without creating a zero-point ledger
entry. A negative integer creates a point debit linked to the refund decision in the
same transaction. The original ticket earning identifies the beneficiary; no customer
is inferred from an anonymous/legacy ticket. Cumulative refund deductions cannot
exceed original earned points or overdraw the current balance. Independent point
corrections cannot expand the original earning cap. This is an explicit per-refund
manager choice, not an invented proportional or automatic refund policy.

Same scoped key replays the original terms/actor; a second decision for a refund or
changed intent is refused. Failed decision writes roll back any staged debit. Signed
history and point-entry links have consistent nullability checks and a nonempty
migration downgrade guard. The manager-only API accepts strict integers and bounded
reason/key fields. Operator UI/recovery, generalized policy automation, actual provider
verification and comprehensive financial accounting remain open.


A ticket-manager scoped payment snapshot now exposes original operation identities,
keys, actors, decimal values, current observations, active authorization protection,
capture application and linked refund loyalty decisions. Prepared means no execution
seal; unknown means a durable seal without an outcome and never implies failure.
Pending is superseded by a terminal observation independently of SQL row order.
Matching context reads all facts under the institute lock. Provider references and
raw webhook material are excluded from the response. The API rejects foreign JWT
institute scope and inaccessible ticket IDs, and returns monetary values as strings.

This read supports recovery after a lost response without issuing another mutation.
The operator recovery UI and configured real-provider mutation transport remain
required; a read-only snapshot does not authorize an external operation or close a
production payment gate. No schema change is needed.


Checkout now includes the read-only ticket payment history and explicit refresh.
It displays exact recorded currency/decimal text, prepared/unknown/pending/terminal
labels, capture application and signed refund loyalty decisions. Unknown protection
is described as a result to recover, never a failed payment. Failed or malformed
refresh hides stale facts. Snapshot validation rejects wrong ticket, duplicate IDs,
unsupported currencies/status-kind combinations, inconsistent protection/application
and malformed loyalty links. The component is keyed by institute/ticket/token;
sequence and lifetime checks prevent a late old session response from replacing the
current history. It performs no POST or external dispatch and releases no commercial
mutation lease. Business mutation protection remains server authoritative.

Headless component tests and production build verify this checkpoint. CUA inventory
still has no browser/app surface, so actual visual/tablet verification is not claimed.
Signed decision mutation/recovery UI, real provider transport and full accounting
remain required before payment/production gate closure.


Signed refund decision recovery now has a dedicated manager-only GET resource under
its original institute and refund intent. Missing decisions return null; missing or
foreign refund intents return scoped 404. Responses include the original immutable
idempotency key, allowing a future mutation UI to distinguish its own lost-response
recovery from another decision with similar visible terms. The read does not create
a decision, debit points or dispatch a refund. Payment routes share institute and
signed actor validation; cashflow and decision resources additionally require the
institute manager role. Whitespace-modified or oversized actor identities are
rejected consistently. No schema change or live adapter is introduced.


Checkout now offers a manager-only loyalty decision form for confirmed refunds with
no recorded decision. Zero explicitly retains points; negative values request a
bounded deduction with a reason. Server policy remains authoritative. The immutable
intent is stored in session storage under institute/ticket/refund/signed actor before
POST. Recovery first reads the dedicated decision resource; a matching original key,
actor, refund, points, reason and entry shape avoids another POST after a lost reply.
A different receipt never confirms the original intention. A missing receipt allows
only the original saved request to be retried. Unknown failures retain frozen terms;
a definitive POST 4xx permits correction. Successful receipt recovery also requires
the application's full data refresh before removing the saved intent and refreshing
payment history. Lifetime/token guards prevent an old context from posting after a
late read, refreshing the current application or clearing its recovery state.

Seven component cases pass in the 62-test frontend regression suite, with a production
build. No real provider dispatch is added. Browser/tablet validation remains open;
the current CUA inventory has no enabled browser or application surfaces.


The operator API now prepares all four operation kinds using a server-owned immutable
binding registry, then dispatches by the durable intent ID. Request bodies cannot
select provider/account/actor or submit a raw parent payment reference. Child requests
name a scoped original authorization/capture intent and resolve its confirmed
reference on the server. Refund preparation and dispatch require the institute
manager. Dispatch recovery additionally requires the original signed actor. Empty
configuration returns 503 and creates no intent or provider result. Account changes
cannot reroute an existing intent. Adapter I/O runs after SQL sessions close; transport
or outcome persistence exceptions return a generic recovery response without leaking
adapter details or inferring failure.

Capture checkout is a separate replay-safe POST with explicit employee and method;
confirmed capture, gift closure, point earning and paid transition retain their existing
atomic transaction. Provider webhook POST reads unchanged bytes with a 64 KiB limit,
then invokes the configured adapter in a worker thread. Authentication precedes SQL;
only the existing correlated atomic receipt/fact writer may acknowledge delivery.
Client verified flags, invalid test signatures and oversized bodies do not create
receipts. There is no public binding registration or default payment adapter. The
application factory accepts explicit trusted bindings; production provider credential
loading, real authentication/transport and operator payment dispatch UI are still
required. Test adapters prove routing and recovery behavior only, not settlement.


Provider callbacks may themselves raise framework HTTP exceptions. These must not
escape as FlowPilot domain rejections: an HTTP 4xx from transport does not establish
authenticated terminal provider failure. A shared adapter-call boundary converts
such exceptions into transport uncertainty before the operator/webhook API handles
them. Domain/preflight HTTP errors raised outside adapter calls keep their original
meaning. Operator responses contain only the generic same-intent recovery message;
private adapter details and headers are not forwarded. Existing execution seals and
refund reservations remain intact. Webhook failures acknowledge no delivery and
create no receipt; the original event may be retried. Only a validated typed provider
outcome can record terminal failure and release the corresponding protection/budget.


Checkout history now exposes original-operation recovery for prepared, unknown or
pending requests. Only the original signed actor sees the action; refund recovery
also requires the manager role. It dispatches the existing ID without a body and
never prepares another request or guesses failure from a timeout. A successful
response is checked against the original ID/kind/value/currency and allowed status;
a fresh ticket snapshot must confirm the same scoped operation/actor and recorded
status before the application's full refresh. A pending response may have advanced
to an authenticated terminal fact while reading; terminal responses cannot regress.
Unknown errors keep the same recovery handle. Lifetime/token guards prevent stale
responses from refreshing or confirming another session. No provider reference is
sent by the client and no commercial mutation lease is released by this control.
Server transaction guards remain authoritative. Three new component cases pass in
the 65-test frontend suite, and the production build passes. Initial operation
preparation/captured checkout controls and actual browser/tablet verification remain
open, as does real provider transport.


Confirmed unapplied captures can now be applied from checkout history by the original
signed operator, using an explicit cashier employee and supported payment method.
The control stores those immutable application terms under institute/ticket/capture/
actor before POST. An unknown response never changes them; remount recovery retains
the original employee/method even if the current selections differ. It checks the
paid response and a freshly scoped snapshot containing the exact actor/value/currency
and applied capture before full application refresh and clearing its saved terms.
Failure or an old-session response cannot clear recovery or confirm the current UI.
The backend still owns the atomic capture/closure/gift/earning transaction. This is
application of an existing captured fact, not another provider charge. Three new
component tests pass in the 68-test frontend suite with a production build. Initial
operation preparation, real provider integration and browser/tablet checks remain
open; no payment or production gate is closed by these component checks.


Checkout now prepares capture/cancel from a confirmed active authorization, and a
manager can prepare a refund from an applied captured operation with an explicitly
entered amount/currency. These controls name only the original scoped parent intent;
provider/account/reference/actor selection remains server-owned. They store frozen
terms and a generated original key before POST. Unknown replies retain the same
request across remount. Definitive preparation 4xx permits correction. Responses
and a freshly scoped snapshot must agree on original intent/key/kind/value/currency/
actor before application refresh and removal of saved recovery state. Preparation
does not dispatch or claim settlement: the existing recovery action sends the durable
operation later, and the server rechecks parent proof and refund budget. Five new
component cases verify capture/cancel/refund lost-response replay, before-POST storage,
changed-value response rejection and cashier refund exclusion. The 73-test frontend
suite and production build pass. Initial authorization UI, real provider integration
and browser/tablet validation remain open.


The initial authorization UI now obtains its exact decimal amount and currency from a
scoped configured-provider quote endpoint. The read holds the institute lock and uses
the existing unpaid quote validator, including gift remainder and declared line prices;
it creates no payment request or provider I/O. Eligible checkout history requests this
quote only after reading a scoped unprotected snapshot without unresolved operations.
A wrong-ticket or malformed read hides the old value. Authorization preparation reuses
the immutable before-POST recovery mechanism with a null parent intent. Saved original
amount/currency/key remain unchanged when a later quote differs. The server rechecks
current quotes for new requests and first execution; original persisted replay never
re-quotes an unknown result. All four operation preparations, original operation
recovery and confirmed captured checkout now have component controls. This does not
close payment gates: real provider authentication/transport, stale unexecuted request
recovery auditing, accounting completeness and actual browser/tablet remain open.


Audit found that hiding initial authorization for any prepared operation could trap a
ticket after an unpaid price edit: preparation does not seal execution, the original
request must retain its old amount, and its first dispatch correctly rejects the now
obsolete quote. Prepared-only history therefore no longer hides a fresh current quote
or an explicitly new request. Unknown/pending operations and active protection still
do. The old request is not erased, rewritten or marked failed. New requests remain
subject to current quote validation; the institute lock and single active execution
protect dispatch. A regression changes the price after preparation, rejects old
dispatch with no I/O, authorizes the current amount once, rejects old retry under the
active execution and verifies both immutable requests remain. The component test
confirms current quote availability with prepared history and its disappearance once
an unknown protected operation is read. No abandoned reservation or timeout-based
release is introduced, and payment/production gates remain open.


The permanent operator HTTP scenario now traverses the complete declared financial
chain: explicit earning policy, authorization, capture, confirmed-but-unapplied
cashflow, checkout application/replay, prepared refund reservation, confirmed refund
and terminal replay, signed manager loyalty correction/replay/read recovery, ticket
snapshot and customer balance. The scenario proves 10.35 CHF captured/applied, 5.00
CHF refunded, 5.35 CHF confirmed net, exactly one capture application and +10/-5 point
entries. A reserved refund does not reduce confirmed net until confirmed, and a point
correction does not alter monetary cashflow. Actor/manager and original reference
requirements remain enforced. The cross-module bundle passes 19 local cases (3
opt-in skips) and 22 with PostgreSQL enabled; HTTP fixtures remain SQLite while the
opted-in domain cases use actual PostgreSQL. This is simulated provider integration,
not browser/tablet verification or bank settlement.

Accounting audit found a remaining production gap in legacy Chiffres:
`get_chiffres_by_employee` sums paid line totals as floats without separating the
original ticket currency. Its totals cannot establish comparable monetary units
when an institute has historical CHF/EUR/unknown tickets. The provider cashflow view
already separates account/currency, but does not repair that service revenue report.
The next independent payment checkpoint must make official service totals unit-safe;
no FX conversion or implicit currency relabeling may be invented. Payment gates and
production readiness remain open.


The identified mixed-unit Chiffres gap is now repaired under ADR-009. Original invoice
currency groups are reported separately; mixed/unknown legacy monetary totals are
null and unknown-unit tickets are counted without invented conversion or relabeling.
This repairs gross service unit aggregation, not bank payouts, fees/taxes or complete
net accounting. Those payment/production verification requirements remain open.


Cashflow consistency is now exercised against concurrent PostgreSQL transactions.
A writer stages a terminal refund outcome without committing; a separate report
reader is observed waiting on a real database lock through pg_stat_activity. After
commit, confirmed refund moves the original reservation to refunded and lowers
net confirmed cash; confirmed failure releases the reservation without reducing
net cash. Neither path mixes pre-commit reservation with post-commit terminal state.
Replaying the original result preserves the same amounts. This verifies the existing
institute-lock boundary, not bank settlement, provider signatures or full accounting.


Pilotage exposes the existing manager cashflow endpoint through a read-only panel.
The UI keeps provider/account/currency groups separate and labels the cumulative
recorded capture/application/refund/reservation/net amounts. It does not imply daily
service revenue, bank payouts, fees or taxes. It formats exact recorded decimal
strings, including values beyond JavaScript safe integer cents. A scoped institute/
token component hides old facts during refresh, rejects malformed or foreign
snapshots, and prevents late disposed reads from publishing. Manager presentation
is only a convenience; the signed server role and institute remain authoritative.
No mutation or provider dispatch is triggered. Three component regressions pass
within the 84-test frontend suite, and TypeScript/Vite build passes. Browser/tablet
visual verification and actual provider/accounting integration remain open.


Cashflow presentation additionally checks the existing ledger relationships in
exact BigInt cents: captured = applied + unapplied, captured = refunded + net,
and refunded + reserved <= applied. These are consistency checks on recorded
server facts, not a client settlement calculation or repair. An invalid account
rejects the entire snapshot; duplicate groups, missing/nondecimal monetary values
and unsupported currencies are rejected too. A subsequent valid read recovers.
Four focused tests, including eight invalid-response variants, pass within the
85-test frontend suite; TypeScript/Vite build passes. Production gates remain open.


Browser payment recovery uses a separate explicitly enabled simulator and owned
temporary database. The simulator records the first authorization and loses its
reply, then returns the original result on replay. Actual signed browser sessions
verify unknown protection, reload, original operation/key recovery, capture and
checkout application in desktop and touch-enabled tablet-landscape Edge. A
read-only same-cashier checkout-start replay is permitted under the institute lock
to reach recovery after reload; every mutation retains the execution guard.
Normal browser fixtures and the production registry remain unconfigured.
This is not a real bank, signed callback or physical-tablet acceptance proof.
