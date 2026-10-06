# ADR-013 — Signed institute supplier identities

Status: accepted for the Phase 10K procurement foundation. Purchase orders,
partial receipts, reorder and forecasts remain required.

Master Plan section 31 requires suppliers and purchase orders. A purchase order
must identify an actual supplier without a fabricated default or a shared,
cross-institute catalogue. Inventory now records an institute-owned supplier
reference and name, plus the manager's reason, signed actor, original request
key and UTC creation instant. References are unique within their institute.
The owner uniqueness constraint supports future composite order foreign keys.

Creation acquires the existing institute lock. Identical same-actor retries
return the original identity; changed reference, name, reason or actor is
refused, as is a second identity with the same reference. This does not create
a stock item, movement, order or outbound supplier communication. No endpoint
rewrites or deletes the original identity. Subsequent supplier maintenance must
preserve references held by recorded purchase orders.

Same-institute managers create; reception and managers read bounded pages and
the scoped original. Missing or foreign identities are 404, while incorrect
role or institute claims are 403. Body-supplied actors are rejected.

The native Inventory directory opens on demand. Its creation request is saved
under institute and signed subject before POST. A lost response can be replayed
after reload with identical terms. Clearing requires matching POST and original
GET results followed by a successful fresh directory read. Later read failures
never turn a committed creation into a safely discardable request. Only a
definitive creation rejection permits an explicit user correction. Old-token
or disposed replies cannot publish facts or clear a saved request.

Migration 0a675be2c4d9 creates an empty table without seeding or backfill. An
empty roundtrip is supported. Recorded supplier identities refuse downgrade
before DDL; existing invoice and inventory histories are also checked before
a lower migration target could cause partial SQLite teardown. This checkpoint
does not close inventory or production readiness gates.
