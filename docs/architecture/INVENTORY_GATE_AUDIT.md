# Inventory requirement audit — Master Plan section 31

Scope: current functional implementation and controlled API/PostgreSQL/Edge
evidence. This is not physical tablet, production migration or production closure.
The broader Phase 24 demand/revenue/inventory/workforce forecast engine remains
distinct from these recorded-source and explicit scenario calculations.

## Requirements and evidence

| Required item | Current behavior and boundary | Authoritative coverage |
| --- | --- | --- |
| Retail, cabine and consumables | Independent institute catalogue; explicit ml/g/whole-unit quantities, immutable SKU/unit/category. No inferred material units or commercial currency totals. | `inventory/models.py`, `schemas.py`, `service.py`; `test_inventory_10a.py`; frontend inventory tests and signed `inventory.spec.ts` |
| Movements | Signed receipts/adjustments and linked actual-consumption debits; exact milli ledger, no negative/over-capacity balance, scoped original-key replay before current budget checks. | `test_inventory_10a.py`, `test_stock_consumption_10f.py`, `test_purchase_orders_10l.py`; actual PostgreSQL competing deductions; native lost-POST recovery |
| Adjustments | Explicit measured signed delta and reason, original actor/request recovery, retained immutable movement history; cashier cannot author. | `inventory.spec.ts` receipt 10.125 then adjustment -6.000, history and threshold 4.125; role/input/rollback API cases |
| Consumption per service | Actual start pins original norm and quantity for every walk-in line and appointment. Manager confirms actual quantities or signed empty measurement only after completion. Atomic all-item budget checks and original replay prevent duplicate debit. Missing basis/norm never becomes an inferred zero. | `test_stock_recipes_10c.py`, `test_stock_execution_basis_10e.py`, `test_stock_consumption_10f.py`, `test_consumption_worklist_10g.py`; native `consumptions.spec.ts`, `recipes.spec.ts`, `walkin.spec.ts` |
| Retained provenance | Invoice removal affects billing but retains original performed line, basis, norm and consumption. Appointment original invoice link prevents later invoice lines from masquerading as original execution. | ADR-011/012; `test_checkout_correction_10h.py`, `test_appointment_invoice_provenance_10j.py`; signed native checkout correction; observed report retained-invoice check |
| Thresholds | At/below threshold alert, exact shortfall and physical stock shown separately from outstanding orders. Equality alerts without fabricating a positive shortage. | `test_inventory_outlook_10n.py`, `outlook-utils.ts`, native `outlook.spec.ts` |
| Suppliers | Scoped signed immutable directory with original actor/key/reason and bounded reads; manager authors and reception reads. No supplier payment/send operation is inferred. | ADR-013; `test_stock_suppliers_10k.py`, migration guards; native `suppliers.spec.ts` |
| Orders | Immutable scoped purchase terms and supplier/item/unit snapshots. Exact receipt facts fulfil original per-item ordered quantities; manual receipts and later stock consumption cannot fulfil an order. | ADR-014; `test_purchase_orders_10l.py`, migration tests; native `orders.spec.ts` lost-reply/order/partial-receipt recovery |
| Forecasts | Original-version explicit volume scenarios; provisional current norms for actual upcoming appointments and opt-in unscheduled queue; measured completed-service constant-pace view with exact duration/quantity arithmetic and explicit incomplete/no-sample coverage. Views are alternatives and never summed. | ADR-015/016; `test_inventory_outlook_10n.py`, `test_inventory_projection_10p.py`, `test_inventory_planned_10q.py`, `test_inventory_observed_10r.py`; native `outlook.spec.ts` and `source-outlook.spec.ts` |
| Reorder | Manager reviews physical threshold/known-demand shortages and conditional arrivals, then explicitly records a purchase order using measured/selected terms. Forecast reads never buy, debit stock or select an unknown norm automatically. | Exact outlook + order APIs; native bounded needs/scenario/source review and order/receipt workflow; role/scope/unit/budget/replay tests |

The four named Phase 10 gates (`INVENTORY`, `SERVICE_CONSUMPTION`,
`STOCK_MOVEMENTS`, `REORDER`) have implemented workflows with the evidence above.
They are not declared production/physical PASS by this document. The literal
HydraFacial quantities in the plan are an example, not approved institute norms.
No recipe is generated from that example.

## Current evidence and remaining acceptance

- Latest frontend/source-review evidence: 141 frontend cases and production
  build; 28 combined signed Edge cases, followed by four final forecast cases
  after view-selector refinement. Desktop and touch-enabled tablet-landscape are
  controlled browser profiles, not a physical tablet acceptance run.
- Latest source/ledger API evidence before Phase 10T: 64 relevant cases with
  PostgreSQL opt-ins enabled, followed by five final observed-source cases.
- Phase 10T adds institute/status/date and queue indexes. Nine focused migration
  and query-plan cases pass, including a default PostgreSQL plan on 6,000
  historical sources. A previously reproduced SQLite blocked downgrade removed
  indexes despite retained purchase facts; migration-local explicit transactions
  now roll back schema and Alembic version together. Index-only downgrade remains
  safe with populated history. No material/source fact is rewritten or backfilled.
- Final full PostgreSQL-enabled backend regression: 489 passed, no failures or
  skips. Four signed Edge booking/walk-in compatibility cases pass with a
  production build. Agenda/planning API day boundaries now use institute civil
  dates; cross-workstation appointment authoring and planning-axis display remain
  a separate UI correction.
  Production data volume, rollout duration/locks, staging backup/restore and
  actual production migration remain unverified. Normal index creation is not a
  zero-downtime/concurrent-index rollout claim.
- Statistical forecast confidence and Phase 24's demand/revenue/workforce
  forecasting are not supplied by a constant-pace calculation or LLM narration.
- The native/browser/API evidence does not close external payment settlement,
  multi-site stock transfers (Phase 25), general
  security/load acceptance (Phase 26), or the rest of the canonical plan.

Independent Workforce requirements may proceed after this inventory audit while
these explicit acceptance gates remain open. See PROJECT_STATUS.md for current
verified counts, checkpoint and remaining scope.
