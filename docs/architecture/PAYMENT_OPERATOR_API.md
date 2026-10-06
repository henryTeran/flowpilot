# Operator payment API

All paths below are relative to `/api/v1/payments/institutes/{institute_id}`.

| Method / path | Authority | Behavior |
| --- | --- | --- |
| POST `/tickets/{ticket_id}/intents` | Institute operator; manager for refund | Persist an immutable operation before I/O. |
| POST `/intents/{intent_id}/dispatch` | Institute operator and original actor; manager for refund | Dispatch or recover the original request against its configured account. |
| POST `/intents/{intent_id}/checkout` | Institute operator and original capture actor | Atomically apply a confirmed capture to checkout. |
| POST `/webhook` | Configured adapter authenticates raw provider input | Commit correlated receipt and outcome together; acknowledge only after commit. |
| GET `/tickets/{ticket_id}/snapshot` | Institute operator | Read prepared, unknown, pending and terminal operation facts. |

## Explicit server configuration

`app.main.create_app(payment_bindings=...)` accepts trusted `ProviderBinding`
instances. `PaymentRegistry` permits one binding per institute. The standard app has
an empty registry. No default or simulated adapter is activated by an HTTP request.
Missing configuration returns 503 without preparing a request or claiming settlement.
Production credential loading and a real authenticated provider adapter remain open.

## Prepare and recover

Preparation requires `kind`, exact positive `amount`, explicit CHF/EUR `currency`,
and a bounded `idempotency_key`. Child operations additionally require
`parent_intent_id`: an authorization for capture/cancel, a capture for refund.
Provider/account/actor/raw payment reference fields are forbidden. Current authorization
quotes and existing parent/refund-budget guards validate the original request. The
signed JWT subject supplies the actor. A returned ID identifies the durable intent.

Save the original terms and key before POST. After a lost preparation response, retry
those terms and key. Dispatch that ID without changing actor or terms. A 503 during
dispatch means recover the same intent: it cannot establish provider failure. Consult
the snapshot, where a sealed request without an outcome is unknown. Pending/unknown
requests retain existing protection and reservations. Terminal dispatch replay uses
the stored outcome without another provider call. Changing the configured account
cannot reroute an old request.

## Checkout and callbacks

Checkout requires explicit `employee_id` and `method` (`cb`, `especes`, or `cheque`).
Only a confirmed matching capture may close the ticket. Original-method replay is
read-only; changing application terms is rejected. Gift closure, point earning and
paid state commit atomically. Refunds require an applied confirmed capture and
remaining reserved budget; a manager must explicitly decide any loyalty deduction.

Webhook input is limited to 65,536 bytes and passed unchanged with headers to the
configured adapter. No JWT or client verified flag authenticates a provider event.
The adapter authenticates before a SQL session opens and returns the original
operation key. The existing receiver validates account, intent, value, reference
and operation kind, then commits the receipt and outcome together. Repeated matching
events return `{ "received": true }`; conflicting facts are rejected. Failed writes
must be retried with the same event identity. Raw secrets are not persisted.

## Verification limits

HTTP tests cover unconfigured refusal, scoped/original-actor/account checks,
immutable preparation replay, unknown recovery, terminal no-I/O replay, server parent
resolution, captured checkout, manager refunds, cancellation release, raw callback
authentication simulation, duplicate receipts and body limits. These tests use an
explicit fake adapter. Separate PostgreSQL domain tests exercise the underlying
transactions and concurrency. Real provider transport, operator dispatch UI and
browser/tablet settlement verification are still required before payment gates close.
