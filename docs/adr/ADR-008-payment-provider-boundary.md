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
