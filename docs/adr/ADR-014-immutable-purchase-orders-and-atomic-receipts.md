# ADR-014 — Immutable purchase orders and atomic partial receipts

Status: accepted for the Phase 10L backend procurement foundation. Native order
and receipt authoring, reorder/forecast reads and complete inventory acceptance
remain required.

Orders belong to an institute and reference its registered supplier. A manager
records an institute-unique internal reference, explicit articles, units and
positive quantities, reason and original request key. Actor and UTC creation
instant come from the signed execution. Supplier reference/name and article
SKU/name/unit are pinned when the order is recorded. At most fifty distinct
articles are allowed. Quantities use the existing exact integer thousandths and
whole-unit rules. Creation records no stock movement and sends no supplier
communication. This is a quantity record, not supplier dispatch, payment or
accounts-payable evidence.

Original order reads contain immutable ordered terms. Fulfilment is a separate
scoped progress read: ordered, received and remaining quantities, with pending,
partial or received state. Received quantities come from signed purchase receipt
facts, not current on-hand stock or unrelated manual receipts. Consuming stock
does not undo a delivery. Future maintenance must preserve these original facts;
there are no order/receipt update or delete endpoints in this foundation.

Receipt creation takes the existing institute lock shared by other stock writers.
Before any durable write it validates every requested article/unit against the
order, remaining quantity and current stock capacity. A receipt header, its
positive receipt movements and entry-to-movement links commit together. Partial
multi-article failure leaves none of these facts durable. A movement may be
linked to only one purchase receipt entry. Composite foreign keys enforce the
institute/order/receipt/item/unit and movement ownership relationships.

Both order and receipt creation return the original for identical same-actor
requests. Different terms, reason, actor or source order under the same key are
refused. Receipt replay precedes today's remaining-quantity/capacity checks, so
completed orders and later stock changes cannot prevent original recovery.
The immutable receipt is separately retrievable by scoped ID. Order and receipt
histories have bounded pages and constant query counts; an institute/order/item
receipt-line index supports progress aggregation without scanning every delivery
in an institute.

Managers create and receive; reception and managers read. Client actors,
unknown units, zero/negative/excess-precision quantities and duplicate articles
are rejected. No supplier, article, unit conversion or consumption rule is
inferred. Native clients must preserve original requests and verify original
reads plus refreshed progress/stock before clearing uncertain writes.

Migration 1b786cf3d5ea adds the tables and movement ownership uniqueness before
dependent receipt foreign keys. It does not backfill purchases from manual stock
movements. Empty roundtrips are supported; recorded purchases or existing
protected histories refuse downgrade before DDL. Owned SQLite/PostgreSQL fixtures
verify unchanged original ledger terms, model parity and guarded history.
No production migration, physical receipt acceptance or full Phase 10 closure
is claimed.
