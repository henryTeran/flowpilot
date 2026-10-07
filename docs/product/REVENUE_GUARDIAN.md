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
| Employee capacity | 14B exposes bounded owned employee occupation evidence; resource/skill constraints and core booking authority remain to integrate. |
| Cancelled revenue | 14C verifies owned booking cancellation events and unchanged original slot terms. Historical quote/price evidence still missing; revenue remains null. Walk-in cancellation valuation remains to integrate. |
| No-show revenue | 14C verifies owned no-show booking events and current terminal source. Original price/quote evidence remains required for financial valuation; no causal loss is inferred. |
| Rebooking opportunities | Reuse CRM/workforce source-backed return/rebooking rules, preserve eligibility and contact permission boundaries. |
| Projected revenue | Explicit deterministic scenario inputs, coverage and confidence; separate estimates from recorded billing. |
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
