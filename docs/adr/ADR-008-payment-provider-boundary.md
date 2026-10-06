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
