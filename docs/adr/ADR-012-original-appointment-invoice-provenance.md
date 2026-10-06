# ADR-012 — Original appointment invoice provenance

Status: accepted for Phase 10J.

Appointment completion creates its invoice header, original line and immutable
appointment-to-line fact in the same institute-locked transaction. The fact
records the original line, signed actor when supplied, and completion instant.
Composite foreign keys enforce appointment/institute, ticket/institute and
line/ticket ownership. No update or delete API exposes this fact. Replayed
completion returns the original handoff without inserting another fact.

Existing completed appointments receive no fabricated provenance. Their mutable
invoice header or matching service is insufficient to identify the original
line, particularly after adding the same service twice. Such inventory work
explicitly reports an unknown invoice link. An unfinished appointment without
an invoice reports not issued.

Inventory work exposes active, removed, not issued or unknown billing context.
Removal time is an explicit UTC instant and is returned only for an invoice
owned by the work's institute. The list remains one bounded UNION query.
Billing context is informational: it neither changes the captured recipe nor
creates zero usage, a debit or a measurement default. Fresh billing context may
change during original consumption recovery; immutable basis and measurement
terms remain authoritative.

Migration f9564ad1b3c8 adds ownership indexes and the fact table without backfill.
An empty table can be reversed. Recorded provenance refuses downgrade before
DDL, as do retained invoice corrections and inventory histories when a lower
target would otherwise lose them. No production migration or deployment is
claimed by this local checkpoint.
