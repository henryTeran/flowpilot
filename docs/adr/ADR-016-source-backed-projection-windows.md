# ADR-016 — Source-backed projection windows

Status: accepted for Phase 10P exact internal time/quantity primitives.
Source aggregation, HTTP contract and native forecast review remain open.

## Decision

Every historical and future boundary is an explicitly timezone-aware instant,
normalized to UTC. Each requested interval is positive and at most 366 days.
The effective future start is the later of the requested start and the captured
generation instant. An already ended horizon is refused. Historical observations
must end no later than generation and the effective future start.

Observed service usage belongs to the half-open interval containing the actual
completion instant, rather than the later manager confirmation instant. Missing
completion timestamps cannot establish membership in that interval.

The internal projection scales measured integer milli-quantities by the exact
elapsed future microseconds divided by observed microseconds. It rounds upward
to one milli-unit for ml/g and to one whole article for unit. Arithmetic uses
Python integers throughout, independently of Decimal precision and floats.
Explicitly confirmed zero may scale to zero; absent measurements do not establish
zero. This primitive does not assess sample coverage or claim prediction quality.

## Next integration constraints

Upcoming unstarted appointments can only use provisional current norms until
actual execution captures an original basis. Waiting walk-ins have no guaranteed
execution time and require an explicit inclusion policy. Historical coverage must
distinguish confirmed bases, pending bases, legacy executions and missing actual
completion timestamps. Source counts and incomplete coverage must be visible.

Scheduled normative demand and a projection of observed usage are alternative
views. Adding them would double-count overlapping future activity. Ordered goods
remain conditional arrivals, separate from physical stock. No projection authorizes
a stock debit, purchase order or autonomous AI action.

## Evidence

Fourteen new primitive cases cover remaining-day clipping, half-open membership,
DST elapsed duration, microsecond ratios, whole-article rounding, large exact
quantities under low Decimal precision, timezone refusal, expired/oversized
windows and invalid measured quantities. Combined with the existing four outlook
cases: 18 passed with PostgreSQL opt-ins enabled. No schema or application data
change, source-backed HTTP forecast or new native UI is claimed.
