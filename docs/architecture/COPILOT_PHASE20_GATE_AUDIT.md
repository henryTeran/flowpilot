# Phase 20 completion audit

Audit baseline: commit524c554, Master Plan §41, signed APIs and frontend inspected9 October2026. This audit preserves all12 initial and4 progressive capabilities. Registering names or passing an isolated test does not close a phase gate. Backend service coverage is distinguished from operator-facing acceptance.

## Initial capabilities and source scope

The authoritative registry/input/evidence guards are `backend/app/modules/copilot/query.py`. Each read returns ANSWER + source EVIDENCE with capture/completion clocks, institute and response SHA. Actions remain empty; neither language nor a read grants execution authority. The official BASE process corpus routes messages; business IDs/dates/scenarios come from explicit UI selections. Provider SDKs are not invoked by these adapters. Missing selections/unsupported routes clarify; unrelated selections and forbidden roles are refused.

| Master Plan requirement | Implemented source contract and honest limits | Targeted evidence |
| --- | --- | --- |
| CLIENT_READ | Owned registered customer identity; excludes phone/internal creation fields | test_copilot_customer_20a.py |
| CLIENT_SUMMARY | Original observed CRM policy/profile, incomplete-history and unavailable-source markers | test_copilot_customer_20a.py |
| CLIENT_REBOOKING_OPPORTUNITIES | Original retained return rule/care anchor, active booking suppression and malformed-source refusal; no contact/booking grant | test_copilot_rebooking_20b.py |
| PLANNING_READ | Original current local-day planning projection; not arbitrary historic/future planning | test_copilot_planning_20c.py |
| PLANNING_GAPS | Original current/future availability engine, optional selected service and original blockers; not a new allocator | test_copilot_planning_20c.py |
| PLANNING_CONFLICTS | Explicit employee OR resource/local day, original bounded cohort and invalid/overdue diagnostics; not exhaustive institute conflict coverage | test_copilot_conflicts_20d.py; test_copilot_resource_conflicts_20e.py |
| EMPLOYEE_CAPACITY | Explicit completed local day, original recorded work/activity coverage; no inferred current physical activity | test_copilot_planning_20c.py |
| REVENUE_SUMMARY | Explicit observed period, original paid-ticket/active-line aggregates, separate currencies and unknown-quality markers; not settlement proof | test_copilot_revenue_20f.py |
| REVENUE_LOSS_ANALYSIS | Original booking closures/walk-in cancellations, full-cohort aggregate and bounded source references; causal financial loss remains unknown | test_copilot_losses_20h.py |
| REVENUE_OPPORTUNITIES | Explicit capacity, rebooking or closures source; original capacity/rules/follow-up readers with full counts and bounded detail; no invented money/contact | test_copilot_opportunities_20g.py; test_copilot_returns_20m.py; test_copilot_follow_ups_20n.py |
| STOCK_READ | Original recorded stock/threshold/pending quantities, first50 catalogue items; pending orders are not received stock | test_copilot_stock_20i.py |
| STOCK_FORECAST | Explicit horizon/service volumes/pinned original recipes, original exact conditional quantities; missing norms remain partial, no inferred demand | test_copilot_stock_20i.py |

Reception discovery exposes only its five authorized initial capabilities; manager-only CRM/capacity/revenue facts are guarded again in dispatch. `test_copilot_audit_20l.py` verifies signed discovery scope, schema digest and operational correlation. `test_copilot_evidence_20j.py` checks capability/source projection binding. SHA proves consistency, not a signature, complete immutable source history or independently verified physical/business truth. These source contracts support scoped answers; broad claims about complete customer, resource, revenue or inventory coverage remain unsupported.

## Progressive capabilities

| Requirement | Actual preparation/execution boundary | Evidence |
| --- | --- | --- |
| APPOINTMENT_CREATE | Explicit booking terms → original domain/resource preview → retained pending operation → separate exact human approval → atomic original booking/resource/event/receipt transaction. Replay recovers historical receipt without another booking. No contact/payment | test_copilot_creation_prepare_20p.py; test_copilot_creation_execute_20q.py |
| APPOINTMENT_MOVE | Explicit owned appointment/new instant/optional employee/service → original domain preview/history binding → pending operation → separate exact approval → atomic original move/resource/event/receipt. Customer metadata preserved; changed sources invalidate approval | test_copilot_move_prepare_20s.py; test_copilot_move_execute_20t.py |
| MARKETING_CAMPAIGN_DRAFT | Explicit retained audience/template plus reviewed digest → original literal template-bound DRAFT. Separate existing marketing review/approval stage chain. No generated copy, implicit approval, contact or delivery | test_copilot_marketing_20v.py; test_marketing_draft_preview_20u.py |
| STOCK_REORDER_PROPOSAL | Explicit owned supplier/items/pending assumption/optional recipe-volume scenario plus reviewed state → separate retained typed proposal. Exact original outlook quantities/partial coverage. No purchase order, quote, supplier contact/payment, receipt or stock movement | test_copilot_reorder_20w.py; test_reorder_migration_20w.py |

CREATE/MOVE share original signed-scope/current-approval/expiry/key/source checks. Booking-specific execution receipts are not reused for marketing or stock. Level2 marketing/stock preparation retains a draft/proposal; it is not a level3 authorization. Separate typed discovery/input/output contracts and operational source digests exist. No broad capability execution, generated SQL or provider-selected IDs are registered.

## Gate gaps that remain required

| Gate | Current conclusion | Evidence still required for closure |
| --- | --- | --- |
| COPILOT_READ | PARTIAL: scoped backend contracts exist for all12 names | Operator UI for authorized consultation, explicit selections, scope/integrity/refusal/clarification rendering and current frontend/backend acceptance |
| COPILOT_SUGGEST | PARTIAL: deterministic rebooking/revenue/stock suggestions exist | Operator UI must preserve partial coverage, bounded counts and conditional assumptions without claiming money/contact/booking authority |
| COPILOT_PREPARE | PARTIAL: all4 progressive preparations exist in signed APIs | Operator UI must review exact selections/source digest and retained results, invalidate stale previews and handle uncertain acknowledgements/recovery per actor/institute |
| COPILOT_EXECUTE_GUARDED | PARTIAL: atomic explicitly approved CREATE/MOVE exist | Operator UI for separate prepare/decision/execute steps, fresh source checks and durable receipt/replay; marketing/reorder must stay within declared preparation-only scope |

Frontend evidence: `frontend/src/App.tsx` main-view/navigation dispatch and `FlowPilotSidebar.tsx` currently have no general Copilot entry. `BaseCancellationPanel.tsx` covers historical cancellation only; it does not prove CREATE/MOVE/marketing/reorder or initial-capability UI. Existing domain panels cannot substitute for proof that the Copilot interaction uses official BASE and these contracts. No UI or phase closure is claimed from backend API tests alone.

## Current packaged backend evidence (20X)

The new image `sha256:92580c1c5b7a6b9b45e3e36a9ff06c9dd4acff4f2ca3dede8fcc868fcde2c470`, tag `flowpilot-copilot-20x-validation`, was built from backend/corpus baseline524c554 using `backend/Dockerfile`. Build validation passed29 BASE resources and54/54 lexical routing examples. Actual runtime versions are Python3.12.15 and Node22.23.3. This supersedes20K for current backend acceptance.

All19 `test_copilot*` modules, appointment creation/move domain preview modules20O/20R, marketing domain preview20U and reorder migration20W ran inside this actual Linux image:64 passed273.90s, zero failures/skips. Actual SQLite and isolated PostgreSQL16 were used; migration tests upgrade/preserve/compare schema and protect populated originals from downgrade. The single warning is the existing passlib crypt deprecation. Test/migration files were mounted read-only; this is not proof of a bundled production migration runner, whole-project acceptance, model quality or a deployed system. Language provider ports remain disabled; no external inference/contact/purchase was performed.

The PostgreSQL test server used a dedicated labelled Docker network and tmpfs data with no host port. After terminal successful completion, temporary fp_test schemas were0. Ownership labels were verified before removing only this server and its network; the test container removed itself. The image remains locally available. Logs are local `.cache/20x-build.log` and `.cache/20x-tests.log`.

UI work remains the next implementation task. Current packaged backend evidence does not close any of the four gates above by itself. Voice and later Master Plan phases remain incomplete; the full26-phase goal stays active.
