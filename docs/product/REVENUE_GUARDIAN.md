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
| Capacity utilization | Reuse workforce work-hours/occupation and core capacity authorities; integrate a pinned institute capture and distinguish recorded activity from complete attendance. |
| Unused capacity | Derive covered free intervals from the same authority, without treating incomplete occupation as proven unused capacity. |
| Employee capacity | Integrate owned employee/resource/skill constraints, not summed nominal minutes. |
| Cancelled revenue | Capture owned cancellation events/retained invoice or booking terms; distinguish declared opportunity value from actual lost revenue. |
| No-show revenue | Capture source-backed no-show status and original price basis; do not invent prices or settlement loss. |
| Rebooking opportunities | Reuse CRM/workforce source-backed return/rebooking rules, preserve eligibility and contact permission boundaries. |
| Projected revenue | Explicit deterministic scenario inputs, coverage and confidence; separate estimates from recorded billing. |
| Opportunities | Each must contain type, evidence, estimated_value, confidence and recommended_action; no automatic booking/contact or official LLM calculation. |
| Product acceptance | Integrate manager desktop/tablet Revenue Guardian view, source navigation, uncertainty/refusal/retry and actual backend native verification. |

Large-cohort memory/load behavior and report-wide evidence navigation remain
unverified: the pure kernel retains unique ticket/line IDs and mix groups even
though SQL reads stream. A bounded page must not be substituted for this aggregate.
Production/device/provider acceptance stays separate from local functional gates.
