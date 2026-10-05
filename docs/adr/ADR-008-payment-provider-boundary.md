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
