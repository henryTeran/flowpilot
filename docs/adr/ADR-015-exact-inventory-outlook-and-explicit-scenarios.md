# ADR-015 — Exact inventory outlook and explicit service-volume scenarios

Status: accepted for the Phase 10N read API and Phase 10O native scenario review.
Scheduled-demand integration, observed-usage projections and complete inventory
forecast/reorder acceptance remain open. This does not close Phase 24 forecasting.

Stock thresholds are recorded minima, not target purchase quantities or supplier
pack sizes. Purchase orders have recorded quantities but no guaranteed delivery
date. Reorder reads therefore expose physical stock, threshold alert/shortfall,
and outstanding quantities separately. No automatic purchase or stock movement
is created. Equality with a threshold remains an alert, even when the shortfall
to reach that exact threshold is zero.

GET `/inventory/institutes/{institute}/outlook` reads a bounded catalogue page.
POST `/inventory/institutes/{institute}/forecast` carries a read-only explicit
scenario: timezone-aware start/end instants (positive, at most 366 days), one to
fifty distinct services, explicit positive whole volumes (at most 100000 each),
and an explicitly selected original recipe ID or explicit null. POST records
no request, stock, recipe or purchase fact. Managers and reception may read;
signed institute/subject scope and existing permissions are authoritative.

Selected recipe versions are scoped to the institute and exact service. Later
revisions never replace them. Known demand sums selected original recipe lines
multiplied by the caller's volumes, using integer thousandths. A disabled selected
norm explicitly contributes zero. A missing selected norm is unknown, including
when another current recipe happens to exist. Partial coverage keeps complete
demand null for every article; known quantities remain a labelled lower bound.
Complete selected-norm coverage concerns only that explicit scenario, never all
real clients, future bookings, unrecorded usage or actual measured consumption.
Dates label the volume scenario; the API does not predict its service counts.

For each catalogue article:

- `threshold_shortfall = max(0, threshold - physical stock)`;
- `known_demand_shortfall = max(0, known demand + threshold - physical stock)`;
- `conditional_shortfall_after_all_orders` subtracts outstanding quantities from
  that second formula, conditional on all recorded orders actually arriving.

The conditional figure is not availability, an ETA promise, sufficient capacity,
an executable purchase quantity or permission to consume stock. Missing delivery
timing, case sizes, conversions and other business policies are not guessed.

Receipt quantities are grouped per original order/article before computing each
remaining quantity. Streaming those ordered rows and summing in Python prevents
receipt join multiplication and large aggregate float/integer overflow. Manual
stock receipts and subsequent consumption never count as purchase fulfilment.
Recipe multiplication also uses Python integers and exact strings, independently
of caller Decimal precision. Reads take the same institute lock as stock, recipe
and purchase writers; a PostgreSQL test observes the reader's actual lock wait
while a purchase receipt is staged, then proves stock/pending reflect one commit.
Queries stay constant per bounded page and scenario; no per-service/item queries.

No schema or existing application database migration is required. Forecast UI
must label scenario volumes, original norm versions, partial coverage and the
conditional order figure clearly. Scheduled-demand and observed-usage sources
will require their own explicit time/coverage contracts before broader closure.

The native view opens bounded catalogue pages on demand and separates physical
shortage from conditional incoming quantities. Scenario date inputs belong to
the institute's named timezone; civil-date resolution roundtrips reject skipped
or ambiguous midnight instead of guessing the workstation's offset. Explicit
volumes and paginated original norm selection require no stock mutation lease.
Norm-read failures can be refreshed without changing the service selection.

Original norm GETs are checked before forecast reads; response versions, states
and quantities must match those saved selections. Exact known quantities are
also compared against selected original recipe lines, not merely against the
response's own arithmetic. Input changes and stock invalidation hide old facts.
Late previous-scope/token/date-context replies cannot publish current results.
These ephemeral read scenarios do not create durable business requests or
prove automatic demand prediction/physical inventory acceptance.
