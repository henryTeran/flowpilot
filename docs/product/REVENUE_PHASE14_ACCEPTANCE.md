# Phase 14 — canonical acceptance audit

Authority: Master Plan section35, architecture foundations, and Definition of Done
section64. Audit started from clean implementation HEAD `16fdb62`; no application
code or schema changes during this checkpoint. Full26-phase objective remains active.
All three functional gates PASS at the controlled local scope below. Production,
physical-device, live-provider and large-cohort/load acceptance are separate OPEN gates.

## Requirements and evidence

The plan says “calculs possibles” and requires each opportunity to contain type,
evidence, estimated_value, confidence and recommended_action. It does not authorize
fabricated prices, physical presence, causal loss or prediction when those sources
are unavailable. Explicit unavailable values are part of the contract, not zeros.

| Canonical item | Implemented behavior and authoritative evidence | Practical limit |
| --- | --- | --- |
| Revenue Guardian | Manager-only Pilotage workspace; billing, capacity, scenarios, booking/walk-in closures, rebooking and current-queue slot review. Nine native specs exercise desktop and touch tablet. | Controlled browser profiles, not physical-device certification. |
| Capacity utilization | `revenue/capacity.py`, occupation/work source services and14B/14L tests: exact recorded busy time intersected with declared employee-time, whole-cohort counts separate from pages. | No attendance proof; incomplete hours/activity refuse an aggregate ratio. |
| Unused capacity | Same kernel exposes recorded unoccupied person-time;14F/14U independently query the sovereign queue/skills/resource engine for an additional arrival. | Person-time is not a physical idle asset or confirmed saleable/reserved slot. |
| Cancelled revenue |14C/H verify booking/walk-in terminal evidence.14G retains commercial basket terms;14I/J/R/S retain historical booking rates and explicit independent valuation decisions. | Commercial terms or declared historical-rate scenarios are not agreed quotes, payments or proven causal losses; cancelled_revenue remains unavailable. |
| No-show revenue |14C/I/J/R/S verify no-show transition, historical reference and explicitly chosen member/passage scenario; retained originals bind source/actor/request. | No execution/physical no-show inferred; no agreed price, eligibility or causal-loss claim. |
| Average ticket |14A/K exact paid-ticket basket totals and rational averages separately per currency, complete only with usable recorded amounts. | Recorded paid flags do not certify bank settlement or all real sales. |
| Rebooking opportunities |14E/V select latest observed completed care under current original CRM rule, exact due time and whole-customer active-return suppression; native rule/permission review. | Estimated_value unavailable; no future service, agreed price, return need, permission-to-send or automatically selected slot inferred. |
| Service mix |14A/K active invoice category/service/currency groups with line counts/units and amount diagnostics; extended line totals are not multiplied again. | Line groups are not basket totals or proof of full real sales coverage. |
| Retail attach rate |14A/K care/retail basket association with explicit missing-line/unknown-category coverage refusal. | Association is not retail-unit ratio or causal effect. |
| Employee capacity |14B/L employee recorded occupation and declared time;14F/U current qualified/resource-constrained additional-arrival projection with explicit horizon. | No opening-hours, physical availability, assignment or reservation proof. |
| Projected revenue |14D/M/N/O/P/Q exact explicit constant-historical-rate scenarios, signed retained originals, key recovery/audit and selected comparisons. | Conditional/unvalidated assumption; no causal lift, summed variants, FX or autonomous forecasting. |
| Opportunity fields | `closures.py`, `walk_in_cancellations.py`, `rebooking.py`, `slot_opportunities.py` expose all five required fields and strict no-action claims. | Null estimated_value honestly records absent price/value evidence. |
| Error, permission and tenant safety | Signed manager/exact-institute routes, strict bodies/aware bounds, invalid-source refusal, frontend cached-proof masking and request/session/unmount guards; source API and DOM/native tamper tests. | No SQL-administrator authenticity claim. |
| Sensitive-action audit | Scenario and closure-valuation declarations retain signed actor/key/request/source/full raw JSON/SHA, independent reads and history. Existing commercial cancellation and booking reference writes retain source terms atomically. | Read-only rebooking/slot review performs no new decision/action. SQL append-only triggers are not claimed. |
| Transaction and concurrency | Original replay precedes mutable recapture; actual PostgreSQL same-key races/serialization, forced rollback/lost acknowledgement, full-cohort/off-page logical verification and guarded migrations. | Does not certify production topology, load or operational recovery. |
| UX and responsive behavior | Explicit reads/financial assumptions, progressive source details, error/retry, real paging and recovery,44px controls/no overflow on desktop/touch landscape tablet. | No portrait/mobile/physical acceptance extrapolation. |
| Deterministic truth | Money, durations, ratios, assumptions and business decisions use existing domain kernels and exact integer/Fraction arithmetic. | No LLM-generated official calculation or validated prediction. |

## Scope correction from previous NEXT statements

Earlier checkpoint notes proposed a new general opportunity-decision store and
additional rebooking price/slot linkage. These were planning hypotheses, not explicit
section35 requirements. Rebooking/slot readers do not declare or execute a human
decision, so the sensitive-action audit requirement does not require another write
or table for merely reviewing them. Sensitive scenario/valuation writes are already
retained and tested. A future actual booking, contact, approval or decision must use
its authorized domain flow and appropriate audit/idempotence; review is not that action.

Likewise, inventing a future rebooking service/price or automatically selecting a
slot would change source meaning.14U offers explicit service/horizon feasibility
review without reservation. Unknown estimated value stays explicit. Individual
invoice navigation and large-cohort optimization may improve the product, but are
not stated as Phase14 gate criteria. They remain identifiable limitations rather
than being silently turned into required speculative features or hidden completion.

## Verification record

Fresh Docker Python3.12 run of all18 Phase14 backend test modules: **64 passed188.02s**,
zero failures/skips, terminalexit0, with SQLite and actual isolated PostgreSQL enabled.
Includes original/reference/cancellation migrations, raw/provenance/amount/claim
validation, full-cohort paging, source ownership/authorization, same-key races and
rollback/recovery. Existing crypt deprecation only. This is the complete Phase14
module suite, not a new whole-project backend regression or production test.

Implementation HEAD's frontend baseline: **402 passed94.09s** at14V, zero failures/
skips, terminalexit0. Source is unchanged during this audit. Native sweep runs each
of the nine Revenue Guardian specs in a separate runner-owned database, rebuilding
the production TypeScript/Vite bundle each time. Mixed-source conversion fixtures
are used only for billing/scenario history/writer; other specs own their source facts.
Fresh native sweep: **18 passed**, nine specs times desktop/touch landscape tablet,
zero failures/skips. Each case exited0; final supervisor reported
`NATIVE_AUDIT_ALL_CASES_EXIT=0` and terminalexit0. Every owned database was removed.
Each independent build passed. Current-source visual QA from14K–14V remains the
visual evidence; this sweep adds fresh integration assertions, not a claim that
every new screenshot was manually inspected. Frontend402 baseline was not rerun.

Local functional decision: REVENUE_GUARDIAN = PASS; REVENUE_EVIDENCE = PASS;
OPPORTUNITY_ENGINE = PASS. This completes the recorded/conditional Phase14 scope,
not production readiness or the entire26-phase objective. Phase15 starts next.

## Open release boundaries

- Alembic head8ef5b643992a is implemented/tested; no persistent application or
  production database was migrated. Deployment must apply the controlled migration.
- No live provider delivery, settlement, real contact, production rollout, physical
  attendance/tablet or production authorization infrastructure certification.
- Whole-project backend regression, production performance/memory/load behavior,
  backup/restore/operational acceptance and subsequent phases remain to verify.
- Canonical section36 Smart Waitlist is next only after the local Phase14 gate
  decision. It is not implemented by a conditional revenue slot projection.
