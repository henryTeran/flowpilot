# ADR-010 — Exact institute stock ledger

Status: accepted for Phase 10 foundation; full inventory gates remain open.

## Context

Master Plan section 31 distinguishes retail stock, cabine stock and consumables,
then requires movements, adjustments, service consumption, thresholds, suppliers,
orders and forecasts. Payment-provider integration is externally blocked. The
autonomous instructions explicitly authorize safe independent work in another
phase. Inventory starts without closing the outstanding payment gates.

## Decision

Inventory is a module of the existing modular monolith. Each article belongs to
one institute and has an institute-unique SKU, explicit category, measurement unit
and nonnegative reorder threshold. The initial units are ml, g and whole units.
There is no implicit conversion between units or between articles. No stock is
inferred from a catalogue entry: its initial ledger balance is zero.

Quantities are stored as signed integer thousandths in BigInteger columns. The
API accepts at most three decimal places and returns exact three-decimal strings.
Whole-unit articles require integer quantities, including their threshold. The
maximum individual quantity and balance is 999999999999.999. This bound keeps
individual database values within signed 64-bit storage. PostgreSQL SUM supplies
the exact ledger aggregate; no binary floating-point quantity is stored.

Receipts increase stock. Manager adjustments apply an explicitly signed delta;
an absolute stock count is not silently interpreted as a delta. Each movement
records the signed operator, reason, timestamp and original idempotency key.
There are no update/delete endpoints for articles or movements in this foundation.
Corrections append a new adjustment; they do not rewrite past facts.

Every mutation acquires the existing institute row lock before reading the
aggregate and recording a movement. A proposed balance outside the allowed range
is refused. Identical retries return the original movement before checking the
current budget. Changed item, kind, quantity, reason or actor under the same key
is refused. A composite foreign key prevents a movement from claiming another
institute's article even if its identifier is known.

Signed same-institute managers create articles, receive stock and adjust it.
Signed same-institute managers and reception operators may read. This follows
the existing operational RBAC boundary; additional staff workflows must be
explicitly scoped when introduced. Responses and histories are bounded and
paginated. Article lookup in another institute returns 404 without exposing it.

Migration a401958c6de3 adds the two tables without altering historical operational
or payment rows. Empty downgrade is supported; a populated catalogue refuses
downgrade before deleting signed inventory history. Tests use disposable databases
or owned random PostgreSQL schemas, never an existing application database.

## API

Under `/api/v1/inventory/institutes/{institute_id}`:

- GET/POST `/items`: bounded catalogue/balance reads and manager creation.
- GET `/items/{item_id}`: article, exact on-hand quantity and threshold indicator.
- GET/POST `/items/{item_id}/movements`: bounded immutable history and manager movement.

List reads use limit 1–200 (default 50) and offset 0–100000. Create requests require
an original idempotency key and reason. There is no client-supplied institute,
actor or initial balance in the request body. Unknown fields are refused.

## Remaining work

This foundation is not full inventory acceptance. Operator UI, versioned service
recipes and consumption facts, supplier/order workflows, explicit receiving links,
reorder decisions and demand forecasts remain to be implemented and verified.
Threshold indication alone is not an automatic purchase order or forecast. No
example HydraFacial recipe is installed as a business default. Consumption and
reversal timing must preserve real performed-service history and concurrent stock
integrity. Stock quantities are neither sale revenue nor proof of procurement
payment. All four Phase 10 gates remain open until their complete scope is proved.
