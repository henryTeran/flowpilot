# ADR-016 — Source-backed projection windows

Status: accepted for Phase 10P exact internal time/quantity primitives and
Phase 10Q recorded upcoming-demand API. Observed-usage aggregation and native
source-backed forecast review remain open.

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

## Recorded upcoming-demand API (Phase 10Q)

POST `/inventory/institutes/{institute}/planned-demand` is a read-only query
available to signed reception and institute managers. It requires explicit aware
`starts_at`, `ends_at` and strict boolean `include_waiting_queue`; extra fields are
refused. Stock pages use the same bounded limit/offset as the existing outlook.
The response records requested and effective UTC starts and generation time.

Unstarted scheduled/confirmed/arrived appointments whose slot overlaps the
effective future interval contribute one service each. Started, finished,
cancelled and no-show appointments are excluded. The end boundary is exclusive.
An arrived appointment whose slot began earlier may still contribute if its
slot has not ended and execution has not started.

Explicit queue inclusion adds the actual quantities of waiting/assigned ticket
lines which are neither removed nor performed. These are an unscheduled queue
snapshot at read time; inclusion does not promise execution within the horizon.
No customer names, phone numbers or actor identities are returned.

Current scoped recipe revisions are provisional at read time. A subsequent
approval legitimately changes this upcoming-demand read; no execution basis is
backfilled. Enabled recipes contribute exact quantities, explicitly disabled
recipes contribute zero, and missing recipes make complete demand null for every
article page. Source counts, missing-norm service quantities and disabled-norm
quantities are explicit. Complete coverage concerns recorded selected sources
only, never future unrecorded walk-ins or actual measured consumption.

The shared institute lock precedes all source, norm, physical-stock and pending
order reads. Query count does not grow with source count. Source and recipe-line
rows stream into integer totals, while returned stock rows remain paginated.
Physical stock, outstanding orders and conditional shortages retain ADR-015's
separate meanings. This API creates no stock, order, recipe or captured basis.

## Evidence

Fourteen new primitive cases cover remaining-day clipping, half-open membership,
DST elapsed duration, microsecond ratios, whole-article rounding, large exact
quantities under low Decimal precision, timezone refusal, expired/oversized
windows and invalid measured quantities. Combined with the existing four outlook
cases: 18 passed with PostgreSQL opt-ins enabled at Phase 10P. That checkpoint
changed no schema or application data and did not add a source-backed HTTP
forecast or native UI.

Phase 10Q adds three planned-demand cases: HTTP source/coverage/security/read-only
behavior, exact large recorded volumes with constant query count on PostgreSQL,
and a verified PostgreSQL lock wait across a current norm revision commit. The
final relevant inventory/source/projection/migration bundle passes all 60 cases
with PostgreSQL opt-ins enabled. The planned-demand API is now implemented;
observed-usage forecasting and native source review remain open.
