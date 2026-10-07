# Revenue Guardian — Phase 14

Authority: Master Plan section 35. Phase status: ACTIVE; all three functional
gates remain OPEN: REVENUE_GUARDIAN, REVENUE_EVIDENCE, OPPORTUNITY_ENGINE.

## 14A: recorded institute billing

Manager-only `GET /api/v1/revenue/institutes/{institute_id}/billing` requires an
explicit aware positive observed half-open period. The signed institute and role
are checked before reading. No public fact injection or write endpoint exists.
The source service holds the shared institute lock, pins one capture clock and
streams every owned paid ticket with a recorded paid date inside the period,
then its active invoice lines. Anonymous/unregistered customers remain valid
institute baskets. Removed invoice lines are excluded. Date comparisons use UTC
on SQLite and PostgreSQL; invoice quantities never multiply already-extended totals.

`revenue/billing.py` aggregates exact integer minor units separately for CHF, EUR
and unknown currency. Known subtotals remain explicit when amounts are missing
or invalid; complete totals and exact rational average baskets are unavailable
for incomplete amounts or unknown currency. Invoice service/category mix is
separate from basket totals; discrepancies are not silently reconciled. Retail
attachment counts care baskets with an explicit retail line, not retail units.
Its ratio is unavailable if any basket has no active line or an unknown category,
or there is no care denominator. Undated paid tickets are diagnosed at institute
scope, because they cannot be allocated to the requested period.

The pure kernel revalidates inputs, including unsafe copied models. Duplicate
ticket/line identities, foreign ownership, substituted capture clocks, out-of-window
paid dates and invalid positive quantities refuse the result. Input facts alone
do not authenticate database capture; the signed service supplies that boundary.
No completeness, settlement, causal lift, physical visit or forecast is claimed.
These are current recorded sources, not an immutable retained report snapshot.
No projection is generated from current catalog prices.

Verification: initial Windows run 11 passed; after API/source addition 12 passed,
1 PostgreSQL test skipped because that local run had no PostgreSQL URL. After final
strict flag/identifier guards and fixing the PostgreSQL fixture's four-value tuple
unpacking, actual Docker Python 3.12 SQLite/PostgreSQL run: **36 passed in 15.82s**,
zero failures/skips, exit 0, including the two new modules and existing CRM billing
and exact-metric regressions. Existing crypt deprecation only. The PostgreSQL test
uses an owned disposable schema. No production migration or frontend acceptance
is implied. The new source test covers 25 tickets, full cohort aggregation,
active/removed lines, quantities, undated/unpaid/end-boundary exclusion and UTC
offset equivalence; the signed SQLite API test covers role/scope/anonymous/date-only,
future-period and unsupported-write refusal.

## Remaining canonical acceptance

| Requirement | Current evidence / required work |
| --- | --- |
| Average ticket | Exact recorded institute basket kernel and signed source API implemented; native review still required. |
| Service mix | Recorded active invoice category/service groups implemented; native evidence drill-down still required. |
| Retail attach rate | Explicit line-classification count/coverage kernel implemented; native review still required. |
| Capacity utilization | 14B adds pinned institute-wide recorded occupation and exact ratio; complete physical utilization and core bookable-capacity integration remain unproven. |
| Unused capacity | 14B computes declared person-time not covered by finalized recorded activity, with uncertainty refusal. This is not proven unused physical capacity or a saleable slot. |
| Employee capacity | 14B exposes owned recorded occupation;14F delegates additional-arrival projections to the core skill/resource/queue authority. Confirmed reservation, opening-hours review and native acceptance remain required. |
| Cancelled revenue | 14C verifies booking events but has no historical quote.14G/H retain and verify walk-in cancellation conditions and full-period currency values; legacy unpriced and source diagnostics remain explicit. No causal revenue loss is claimed. |
| No-show revenue | 14C verifies owned closures;14I/J retain and verify catalog references and expose explicit historical-rate closure scenarios. A benchmark is not an agreed quote, eligibility proof or causal loss. Native review and retained scenario audit remain required. |
| Rebooking opportunities | 14E adds a pinned full-customer CRM candidate catalog, due-rule selection and active-return suppression. Native review, price/scenario valuation and feasible-slot integration remain required; no contact authorization is inferred. |
| Projected revenue | 14D implements a signed exact constant-historical-rate preview with explicit period/currency/activity assumptions and source coverage refusal. Native review and durable scenario audit remain required. |
| Opportunities | 14C adds two source-backed unpriced closure follow-ups with all five required fields. Rebooking/scenario/feasible-capacity opportunities and historical price basis remain to integrate. No automatic contact/booking. |
| Product acceptance | Integrate manager desktop/tablet Revenue Guardian view, source navigation, uncertainty/refusal/retry and actual backend native verification. |

Large-cohort memory/load behavior and report-wide evidence navigation remain
unverified: the pure kernel retains unique ticket/line IDs and mix groups even
though SQL reads stream. A bounded page must not be substituted for this aggregate.
Production/device/provider acceptance stays separate from local functional gates.

## 14B: institute recorded occupation capture

Manager-only `GET /api/v1/revenue/institutes/{institute_id}/capacity` accepts an
explicit observed institute civil `day`, with employee offset and limit20/max50.
A valid institute timezone and positive already-observed day are required; an
invalid zone, skipped day or future/full unobserved day is refused. DST bounds
come from the existing institute calendar. Signed role/institute checks precede
the read; no public capture-clock input or write route exists.

Existing workforce work-hours/occupation readers accept an optional internal
capture clock, supplied only by this locked service. Their public routes and
default behavior remain unchanged. It queries all owned employees, including
unavailable historical staff, at the same capture, and aggregates their existing
union/intersection calculations without substituting returned pages for totals.
Bounded employee rows retain existing occupation/work-hours evidence and source
page totals; full underlying source navigation remains in workforce readers.

Returned known declared-union, covered-busy and outside-work durations are exact
integer microseconds. A recorded unoccupied duration and exact utilization ratio
are available only if every owned employee has usable declared hours and no
candidate activity diagnostic. Missing hours or an uncertain employee outside the
returned page invalidate the entire ratio/free-duration claim. Known subtotals
remain visible. These are summed person-time, not feasible resource slots;
complete attendance/activity stay false and physical-unused/bookable capacity
and money estimate stay null. Missing activity with no date cannot be attributed
to this day; the record is not complete physical truth. Opportunity estimation
must still use owned skills/resources and the core capacity authority.

The aggregate currently performs workforce reads per employee and proves no
large-roster/load target. Each source may contain more originals than its evidence
page. No source/row amount is projected from unused minutes. No UI acceptance is
claimed at this checkpoint.

The 14A SQLite source test's bootstrap tuple was corrected to use the actual
service ID rather than an employee ID. The PostgreSQL fixture already used the
proper service. New capacity/source/billing plus occupation/work-hours regression
run: **23 passed37.18s**, SQLite and actual isolated PostgreSQL, zero failures/skips,
exit0. This preceded final timezone/skipped-day guards; their final focused result
is recorded in PROJECT_STATUS.md. Tests cover more than20 employee rows, identical
whole-cohort aggregates across pages, one pinned clock despite a different default
work-hours clock,25-hour DST day, unfinalized off-page activity refusal, empty/missing
hours, future/calendar/bounds and strict nonliteral flags; signed API role/scope,
anonymous and unsupported writes refused. Existing crypt deprecation only.

## 14C: booking closure evidence and unpriced opportunities

Signed manager-only `GET /api/v1/revenue/institutes/{institute_id}/booking-closures`
requires an explicit observed half-open start/end period and offset/limit20/max50.
It pins one locked capture and streams the entire selected event-time cohort,
returning bounded follow-up opportunities and full-period cancellation/no-show
counts. The basis is **when the closure was recorded**, not the scheduled slot day.

Each event must have one owned appointment and employee, a supported original
scheduled/confirmed/arrived status, matching terminal current snapshot and exactly
unchanged service/employee/customer/slot/booking terms. Actual execution/invoice
linkage, substituted snapshots, duplicate terminal events (even outside the
requested period) or malformed/off-page selected sources refuse the entire read.
Original event ID, actor (possibly absent for legacy data), appointment ID,
before/after terms and clocks remain explicit. No customer name/phone/free text
is projected. These checks authenticate neither arbitrary administrator SQL nor
a complete predecessor history. Complete booking history and causal loss remain
false. Current terminal appointments with no event receive a separate institute-wide
diagnostic, because a closure recording time is unknown; they are not assigned
silently to this period.

Existing BookingEvent snapshots retain no original quoted price. Consequently
both cancelled/no-show revenue and each estimated_value remain null. Current
catalog prices, which can change, never substitute for historical agreed terms.
The two opportunity types recommend reviewing booking and contact permission
before follow-up, with confidence `recorded_closure_only_unpriced`. Reads execute
no contact, reservation or lifecycle mutation. Future valuation must add an
explicit source-backed price basis or clearly separate scenario assumptions;
this checkpoint does not complete the financial opportunity engine.

Initial all four revenue modules: **18 passed19.00s**, SQLite and actual isolated
PostgreSQL, zero failures/skips, exit0. Expanded pure refusal and deterministic
off-page selection tests:8 passed5.68s before final employee-ownership join.
Final focused result after that join is recorded in PROJECT_STATUS.md. Source
tests create25 actual service cancellations/no-shows, prove20/5 pages/full counts,
legacy undated closure diagnostics, catalog-price independence, event-time end
exclusion, corrupted off-page original and duplicate outside-period refusal,
scope/clock/snapshot/execution/current-source substitutions, strict no-action
flags and signed role/institute/anonymous/date-only/bounds/write refusal. No
schema migration, new message, forecast or native UI acceptance is claimed.

## 14D: explicit future gross scenario

Manager-only `POST /api/v1/revenue/institutes/{institute_id}/scenarios/revenue-preview`
accepts an explicit `constant_recorded_gross_rate_v1` model, aware observed and future
start/end periods, one known currency and declared activity fraction between0and1.
There are no default assumptions, no injected source amounts/capture clock/actor,
and no persistence or external action. Signed actor comes from authentication.
The same institute-locked billing source recaptures the entire observed cohort.
Projection start cannot precede capture; both periods must be positive and ordered.

Hypothetical gross = observed selected-currency gross / observed duration × future
duration × declared activity fraction. Exact integer/rational arithmetic avoids
float/Decimal context rounding and currency conversion. Forecast output remains
separate from recorded billing, which still has projected_revenue=null. Confidence
is `conditional_unvalidated_scenario`, validated_prediction/retained/action_executed
are strictly false. This does not price cancelled/no-show bookings, prove recovery,
or validate demand/capacity. No margin, settlement, seasonality, causal or model
quality is inferred from historical gross alone.

Unknown currency sources, institute-wide undated paid records, absent selected
currency or incomplete selected-currency amounts make the projection unavailable
with an explicit reason, rather than zero. An explicitly declared zero activity
fraction produces zero only from otherwise complete sources. A historical window
is not silently extended to capture; its exact rate basis remains in the response.

Billing amount-group invariants now enforce diagnostic partitions, Numeric(10,2)
known-source bounds, complete total/average coherence, unique currency coverage,
service line counts/quantities and retail-ratio coverage. Unsafe copied aggregate
models are revalidated before scenario calculations. The pure kernel cannot prove
source authenticity from structure alone; the signed source service provides that
boundary, and the endpoint forbids caller billing injection.

Initial five-module revenue run: **31 passed24.14s**, SQLite and actual isolated
PostgreSQL, zero failures/skips, exit0, existing crypt deprecation only. Final
expanded scenario happy-path/API/PostgreSQL fresh-source test result is recorded in
PROJECT_STATUS.md. Tests cover exact fractional gross under low Decimal precision,
all unavailable reasons, explicit zero, malformed time/scope/actor/assumption and
corrupt aggregate refusal, strict no-action claims, signed permissions and injected
billing/actor/date-only refusal. Fresh previews can reflect changed current recorded
baskets; an older in-memory response does not mutate. Native UI, retained scenario
original/key/audit/replay, feasible-capacity and source-backed booking-price valuation
remain open; these are preview results, not persisted official forecasts.

## 14E: observed rebooking opportunities

Manager-only `GET /api/v1/revenue/institutes/{institute_id}/rebooking` captures all
owned registered customers at one institute-locked instant. It reuses CRM's current
immutable automation policy and source-backed actual-care candidate derivation,
with an internal optional clock pin. Public CRM routes retain their prior behavior;
neither endpoint accepts a caller capture clock. There is no new timing heuristic.
Only the current enabled, due rebooking candidate for latest observed care is listed.
Scheduled/disabled/missing-candidate customers and relevant policy/registration/care
diagnostics remain explicit. Incomplete care sources prevent that customer's inferred
recency, as in the existing CRM authority, rather than treating the valid subset as
a complete care history.

A due customer with an owned active return booking that overlaps the capture or
ends later is suppressed. This is an explicit generic-return policy, independent of
service mix or appointment credit; it does not prove that a booking was caused by
the original care. Invalid active slot or foreign/missing employee/service evidence
refuses the entire catalog, including if the affected customer lies outside the
returned opportunity page. The already-booked count is for otherwise-due candidates,
not a census of every customer with any booking.

Offset/limit20/max50 bound returned opportunities, not the examined customer
cohort, diagnostics or total. Each exposes the selected care anchor/candidate,
current policy original, registered customer clock, lifecycle original or explicit
unavailability, relevant diagnostics and required type/estimated_value/confidence/
recommended_action. Unrelated package/birthday anchors and full history are not
copied into the response. No name/phone is projected. Monetary value remains null;
confidence is `observed_care_and_declared_rule_only`. Recommendation requires human
review of return need, contact permission and feasible slot. A legacy lifecycle
declaration is not registered marketing-channel delivery authority. Complete history,
delivery and message-sent claims are strictly false; there is no event capture,
booking/contact write or outbound execution.

Initial new catalog plus existing CRM event-source/candidate regressions:
**12 passed25.24s**, SQLite and actual isolated PostgreSQL, zero failures/skips,
terminal exit0. After reducing response evidence and extending scheduled/disabled
policy transitions, final focused **2 passed13.90s**, same two databases, exit0.
Existing crypt deprecation only. Tests create25 actual care-linked customers,
prove20/5 pages/full totals, absent-policy diagnostics, one pinned clock despite a
different default CRM clock, absent contact declarations, active-return suppression,
malformed off-page slot refusal, corrupt actual-care diagnostics, empty terminal
page, bounds/strict flags and signed role/institute/anonymous/write refusal.

The source authority still scans care history and performs reads per customer;
large-customer/load acceptance is unproven. No native Revenue Guardian interface or
retained opportunity audit is claimed. Scenario/price valuation, core feasible-slot
authority, source drill-down and desktop/tablet review remain open.

## 14F: core projected additional-arrival opportunity

Manager-only `GET /api/v1/revenue/institutes/{institute_id}/capacity-opportunity`
accepts an active catalog service and explicit positive future horizon. Under the
institute lock it pins one clock and obtains duration from that service, then calls
the existing sovereign `waiting_projections` authority for a new arrival behind
existing queue commitments. There is no independent availability optimizer or
caller-provided employee/duration. Skills, active sessions, appointments, absences,
resource needs/timelines and queue ordering remain the core engine's responsibility.
Legacy machine-required service without explicit resource needs is unavailable.

An opportunity is returned only when the core projects a positive exact-duration
slot starting at/after capture and ending inside the horizon. Missing/unknown
capacity or a slot beyond the horizon is explicit and has no invented time/value.
Evidence includes service duration, required skills/resources, projected employee
and start/end, capture/horizon and prior-queue/unprojectable counts. No monetary
price is inferred from a slot. The five required opportunity fields are present,
with confidence `conditional_current_queue_projection`, null estimated value and
human opening-hours/current-capacity review recommended before assignment.

This is a current conditional estimate, not a reserved appointment or resource
commitment. The core does not certify future attendance, opening hours or an
unlimited saleable-capacity total. Persisted assignment/booking must rerun its
existing authoritative guards. Neither capacity_reserved nor action_executed may
be claimed. Recorded person-time metrics remain separate from this projection;
the two observations are not summed or presented as interchangeable proof.

Initial new SQLite/PostgreSQL source tests plus existing queue/joint-resource
regressions: **18 passed20.99s**, zero failures/skips, terminal exit0. Final focused
source tests additionally isolate missing resource with qualified staff and
maintenance resource rejection; result is recorded in PROJECT_STATUS.md. Tests
cover missing machine configuration, skill loss, explicit room need, queue FIFO,
an appointment that shifts a full-duration fit, horizon refusal, strict no-write
flags and signed role/institute/anonymous/date-only/unsupported-write controls.
Existing crypt deprecation only. Fixture data is disposable owned source data;
no real assignment, provider message, schema migration or native UI acceptance is
claimed. Retained price/scenario audit and complete Revenue Guardian product
acceptance remain open.

## 14G: commercial terms retained at new walk-in cancellation

New `QueueEvent.cancellation_terms` stores a canonical full-frame SHA256 envelope
for newly recorded `queue.cancelled` events. Capture occurs in the existing
institute-locked cancellation transaction before its commit; it includes institute,
ticket/customer IDs, predecessor/terminal status, event time, optional actor,
recorded basket currency/amount quality and original invoice-line quantities,
durations/categories/unit/extended amounts/removal markers. No current catalog
price is fetched or substituted. Signed route passes its authenticated subject;
internal callers may have no actor, which remains explicitly absent.

Basket and line amounts remain independent source terms, without recomputation
or multiplication of already-extended totals. Missing/invalid/unknown source
amount/currency remains diagnosed. Shared `money.amount_fact` contains the prior
unchanged exact Numeric(10,2) classifier; CRM reexports it for caller compatibility.
This removes a potential ticket-to-CRM/revenue dependency. The capture stays in
the ticket domain; Revenue Guardian will consume its retained source.

Existing cancellation retries return the terminal ticket before a new capture,
so a different retry actor does not replace the original event/price. Commit
failure rolls back both terminal state and snapshot. Later current ticket/line
corrections cannot mutate the stored JSON. The fingerprint verifies complete
frame consistency, not cryptographic authenticity against arbitrary administrator
SQL. No database append-only trigger is introduced. It records commercial value
at cancellation, not paid revenue, confirmed physical loss or a counterfactual
sale. realized_revenue and causal_loss_proven are explicitly false.

Alembic head `5bc2e310669d`, parent `4ab1d209558c`, adds a nullable JSON column.
Legacy events remain SQL NULL with no fabricated price history. New ORM None is
SQL NULL rather than JSON null. Online downgrade is permitted only when no
retained snapshot exists; offline or nonempty-history downgrade refuses deletion.
The migration has not been applied to any application/production database;
deployment must migrate existing schema before starting the new application code.

New source/migration plus ticket workflow and CRM billing/metric regressions:
**40 passed46.64s**, SQLite and actual isolated PostgreSQL, zero failures/skips,
terminal exit0, existing crypt deprecation only. Tests prove signed-route actor,
exact historical basket/line terms, retry single event, independent current-price
change stability, forced transaction failure rollback, migration metadata parity,
empty/legacy-null down-up, history-preserving refusal and offline refusal.
Compatibility evidence for the previous marketing conversion migration and
trusted invocation head checks is recorded in PROJECT_STATUS.md. No new native
UI or financial-loss aggregate acceptance is claimed; Revenue Guardian reader,
booking historical quote and retained scenario/opportunity audit remain open.

## 14H: verified walk-in cancellation value

Manager-only `GET /api/v1/revenue/institutes/{institute_id}/walk-in-cancellations`
requires an explicit observed half-open event-time period and offset/limit20/max50.
One locked capture streams the entire selected cancellation cohort; all original
proof and currency aggregation complete before publication, independently of the
returned page. Current event/ticket state must be owned and terminal with one
supported cancellation event, including a duplicate check outside the period.
Current ticket/line prices are never compared to or substituted for original money.

Retained envelopes require the exact whole stored JSON fingerprint, typed complete
terms, owned institute/ticket/previous-state/event-time binding, coherent known/
missing/invalid amounts, unique ordered lines, positive quantity, valid duration
and nonfuture removed-line clocks. Full original JSON is preserved in responses;
typed datetime rendering would otherwise change `+00:00` into `Z` and invalidate
the returned original digest. Typed validation is applied separately without
changing those original term spellings. Extra or malformed stored fields, changed
fingerprint or substituted source anywhere in the cohort refuse the entire read.
This is consistency/source binding, not authentication against administrator SQL.

The summary separates retained terms from legacy events lacking a snapshot and
groups recorded cancelled commercial values by CHF/EUR/unknown currency, with
exact integer minor units and missing/invalid amount diagnostics. Per-currency
complete values describe only that retained cohort; legacy currency is unknown
and cannot enter a guessed group or complete all-cancellation amount. No FX or
quantity multiplication occurs. An opportunity has a monetary estimated_value
only for known amount plus known currency, explicitly based on recorded cancelled
commercial value. Otherwise it remains null. Confidence distinguishes retained
terms from legacy unpriced events. Human source review is recommended; no recovery
action executes. cancelled_revenue remains null and causal_loss_proven false.

Initial new reader plus ticket snapshot and billing regressions: **16 passed11.73s**,
SQLite and actual isolated PostgreSQL, zero failures/skips, terminal exit0. Final
focused tests after strict no-action and fresh ORM read guards are recorded in
PROJECT_STATUS.md. Tests create25 actual service cancellations plus one legacy
event,20/6 returned pages, full26 count/currency diagnostics, known/missing/invalid/
unknown/EUR cases, intact response original fingerprint, current-price mutation
stability, end-boundary exclusion, corrupt off-page frame, malformed/foreign typed
terms even with recomputed hash, outside-period duplicate and signed role/institute/
anonymous/date-only/bounds/write refusal. Existing crypt deprecation only. No
new schema, native UI, paid-loss or production acceptance is claimed. Booking
quoted-price evidence, scenario/opportunity audit and desktop/tablet review remain
open.

## 14I: historical booking catalog reference

BookingEvent.price_reference now retains a canonical full JSON SHA256 envelope
when a new reservation selects a service or a modification changes its service.
The capture is in the existing institute-locked booking/resource transaction,
bound to the event ID/type/time, appointment/institute/service and optional actor.
It retains service duration and both member/passage catalog amounts with known/
missing/invalid diagnostics. No rate is chosen implicitly for the customer.

Denomination comes only from explicit owned institute currency configuration,
with its updated clock and actor retained. Absent/missing-clock/future configuration
does not label an amount with an inferred currency. Catalog changes or currency
changes cannot rewrite an old event. Idempotent creation replay returns the
existing reservation before a new catalog read/capture. Note, customer or calendar
changes alone do not reprice the reference; selecting another service creates
a separate reference. Cancellation/no-show never captures today's catalog price.

This is a historical catalog benchmark, not proof of an agreed quote, membership
eligibility, consumed benefit, invoice total or paid amount. agreed_quote and
paid_price stay false. Financial valuation must select an explicit source-backed
rate or declared scenario basis and preserve that distinction. No original price
is fabricated for legacy bookings. Private reference data is not added to the
current high-frequency AppointmentRead product flow; a verified manager evidence
reader and future valuation remain to implement.

Alembic head `6cd3f421770e`, parent `5bc2e310669d`, adds nullable JSON with ORM None
as SQL NULL. Empty/legacy-null down-up is permitted; offline or retained-reference
history downgrade is refused. No application/production database was migrated.
Deployment must migrate the schema before starting the new application code.

Initial reference/source/migration and existing booking-checkout regressions:
**7 passed29.03s**, SQLite and actual isolated PostgreSQL, zero failures/skips,
exit0. Final currency-provenance/future-configuration and previous cancellation
migration/trusted-invocation compatibility results are recorded in PROJECT_STATUS.md.
Final forced booking-transaction failure source tests:2 passed6.31s, SQLite and
actual isolated PostgreSQL, exit0; rollback removes both booking and price event.
Tests prove historical two-rate amounts, event binding, actor, creation replay
after catalog/currency change, no note-only reprice, service-change new reference,
missing member amount, no cancellation reprice, metadata parity and data-preserving
migration guards. Existing crypt deprecation only. No frontend, financial-loss
aggregate, signed quote agreement or production acceptance is claimed.

## 14J: verified booking reference and explicit closure value

Manager-only `GET /api/v1/revenue/institutes/{institute_id}/appointments/{id}/price-references`
pins a locked capture and verifies every retained reference before returning
offset/limit20/max50 originals. Full original JSON/digest is preserved. Typed terms
bind institute/appointment/event/type/time/actor, selected service, nonexecuted
booking before/after states, actual service change and amount/currency diagnostics.
Future events, duplicate creation and corrupted sources outside the displayed page
refuse publication. Missing legacy service-selection snapshots are counted without
backfilling prices. Current catalog prices, current service selection and terminal
appointment status do not rewrite historical references. The reader is not a
complete authenticated predecessor-chain attestation.

Manager-only `POST .../appointments/{id}/closure-value-preview` requires explicit
reference event ID/full expected fingerprint, closure event ID, member/passage
rate and reason. Actor comes from the signed session. It verifies owned sources,
one terminal closure/unique creation, reference not later than closure, same
service, retained closure transition and current final snapshot. No automatic
latest-reference or eligibility-based rate selection exists. The selected catalog
benchmark yields exact known-currency minor units only; missing/invalid rate or
unknown currency returns null value with an explicit reason. Current catalog or
currency changes cannot reprice the chosen original.

This produces the five required opportunity fields with confidence
`declared_rate_scenario_not_agreed_quote`. It remains an unretained human-declared
scenario: no quote agreement, eligibility, paid price, causal loss or recovery
action is claimed. No caller-provided amounts or actor are accepted. The closure
must be observed strictly before capture; no clock is advanced artificially to
admit an event at/following the capture. Human review of actual agreement,
eligibility and recovery is recommended before any action. Persisted scenario
original/key/audit, aggregate selected-scenario reporting and native review remain
to implement.

Initial reference reader plus price-capture/closure regressions: **12 passed21.94s**,
SQLite and actual isolated PostgreSQL, zero failures/skips, exit0. Initial combined
reader/valuation4 passed18.26s; final strengthened reader/source-uncertainty result
is recorded in PROJECT_STATUS.md. Tests exercise25 actual creation/service-change
references20/5, full cohort/off-page refusal, intact response SHA, malformed foreign/
actor/quote/currency terms even with recomputed digest, current-price independence,
legacy-null coverage, terminal appointment history and signed manager/role/scope/
anonymous/bounds/write controls. Valuation tests select exact987member/1234passage,
keep historicalCHF after liveEUR/price changes, reject wrong fingerprint/closure/
reference/actor and injected amount, and return explicit unavailable states for
missing/invalid rate and future currency configuration. No schema or native UI
acceptance is claimed at this checkpoint; full Phase14 gates remain OPEN.

## Phase14K — native recorded-billing review

Pilotage/Chiffres now contains a lazy manager-only Revenue Guardian section.
No report loads on mount: the manager explicitly chooses completed institute
civil dates (start included, end excluded), resolved through the institute timezone.
The native form requests the existing signed owned billing reader and validates
the entire response before displaying its original window/capture, paid-ticket
count and separate CHF/EUR groups. Monetary formatting uses BigInt minor units;
a fractional-cent average is explicitly approximate. Unknown currencies do not
receive a monetary label. Missing/invalid amounts preserve partial subtotals and
unavailable averages. Category coverage, care/product attachment, active-line
service mix and institute-wide undated-paid diagnostic remain distinct.

Whole-frame validation covers exact keys, scope, observed time bounds, strict
no-claim flags, safe counts, amount partitions/bounds/completeness, unique currency
groups, active-line counts/units and category ratios. A malformed reread hides the
old report and offers retry; edits, context/session replacement and unmount discard
late responses. This is response contract checking, not a cryptographic proof of
complete sales. No receipt settlement, prediction or causal attribution is asserted.
The section is read only; no schema, business record or external messaging changes.

TypeScript/Vite build passed. Full frontend suite: **368 passed126980.58ms**, zero
failures/skips, terminal exit0, including four contract/React tests for exact money,
incomplete/unknown coverage, explicit read, invalid reread, roles and stale results.
The actual-backend browser fixture reuses owned historical paid-source records;
the backend is real and external providers are fake, with no external delivery.
Final no-known-amount wording was checked with **4 focused tests3.26s**, then a
fresh harness rebuild and native actual-backend **2 passed52.5s**, zero failures/
skips, terminal exit0. Desktop1440x900 and touch tablet1024x768 captures were both
visually inspected; controls are at least44px and there is no horizontal overflow.
BrowserLosAngeles still requests instituteZurich midnights. Six actual historic
paid tickets retain CHF370.35/average123.45, unknown currency and missing/invalid
EUR amounts; the isolated undated-paid diagnostic is1. Corrupt settlement claim
refuses the whole frame and retry restores real source values. Native source mix
is empty in this fixture; nonempty mix remains React contract coverage only.
The initial desktop five-second assertion expired while the full suite ran; tablet
passed. Both reruns with explicit15s assertions passed; initial run is not claimed
as PASS. The final owned temporary database was removed. Existing passlib-bcrypt,
Starlette and color warnings did not fail the final run.
All Phase14 gates remain OPEN: this checkpoint covers recorded billing only,
not native capacity, closures, rebooking, retained scenarios or the full opportunity
review flow. Production, physical settlement and load acceptance remain separate.

## Phase14L — native recorded-capacity review

The manager can now explicitly read a completed institute civil day in Pilotage,
alongside recorded billing. All-employee totals remain separate from the20-row
employee evidence page: known declared work union, finalized activity inside and
outside declared hours, conditional declared time without recorded activity and
exact utilization ratio. Unknown hours/activity suppress derived totals and ratios;
these diagnostics may overlap. Sum of employee-time is not physical unused capacity,
opening hours or bookable availability. No financial value is inferred.

Source details expose the visible original work declarations and at most one
activity source per employee, with full source counts and bounded coverage stated.
Each new employee page is a new pinned backend read, not a retained snapshot across
navigation. Whole-response verification binds scope/day/timezone and exact civil
midnights/capture, all aggregate and page counts, unique ordered employee IDs,
duration bounds, exact derived ratios, strict no-claim flags and nested occupation/
work-hour evidence. Existing occupation verification accepts an explicitly requested
one-row evidence page; its default public20-row contract remains unchanged. Full
employee pages covering the whole cohort must reproduce aggregate sums; partial
pages cannot replace the institute denominator. This does not attest SQL authenticity
or a complete physical activity history.

No reads occur on mount. Malformed reload clears previous totals; date/context/
session changes and unmount discard pending results. This checkpoint is read only,
with no database schema, production migration or external communications.

Initial focused regressions:10 passed5.87s and TypeScript/Vite build PASS. Initial
actual-backend desktop/tablet2 passed1.2m, but visual inspection exposed an inherited
workspace grid narrowing the fourth section to310px. Both Revenue sections now span
the workspace and the native test asserts at least600px width,44px controls and no
horizontal overflow. Final full frontend: **371 passed79899.95ms**, zero failures/
skips, terminal exit0, including pending-session/context replacement guards.
Fresh native rebuilt desktop1440x900 and touch tablet1024x768: **2 passed1.2m**,
zero failures/skips, terminal exit0. Both final viewport captures were visually
inspected; full-width sections, at least44px controls and no horizontal overflow
passed. Actual owned25 then46 employee cohorts use signed work-declaration services
to retain one hour plus one microsecond per employee on the25-hour institute day;
browserLosAngeles does not alter the Zurich day. Missing-hours initial aggregate
is unavailable; all-declared totals retain exact person-time and recorded zero
activity ratio. Next/previous20-row pages preserve all-employee totals; original
work-source details, strict presence-claim corruption refusal and retry verified.
The native historical activity cohort is empty; nonempty occupation/microsecond/
uncertainty proof remains contract/React and existing occupation regression coverage,
not native physical execution proof. Owned temporary database was removed. Existing
passlib-bcrypt and color warnings did not fail the run.
All three Phase14 gates remain OPEN; native closure/rebooking/scenario/opportunity
review and retained scenario/audit/selected-scenario reports are still required.
