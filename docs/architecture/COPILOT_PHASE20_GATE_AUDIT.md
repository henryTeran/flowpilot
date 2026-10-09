# Phase 20 completion audit

Capacity UI increment: EMPLOYEE_CAPACITY now accepts explicit completed day and validates original recorded-capacity source, clock, scope and hash. Build/combined Copilot-capacity10 tests pass; real API/BASE browser acceptance pending. Five other initial UI capabilities and four progressive flows remain outstanding; no phase completion claim.

Rebooking browser evidence: official BASE/real signed API unavailable-source case passes desktop/tablet in8-test suite (1.4m); selected customer, null care candidate, diagnostics/no authority/no phone/only query POST verified. Screenshots inspected and fixture cleaned. Due/already-booked browser acceptance is still pending; phase remains partial.

Rebooking UI increment: selected-customer CLIENT_REBOOKING_OPPORTUNITIES now renders verified original rule/care dates, active bookings and uncertainty diagnostics without booking/contact authority. Build and targeted six-test Copilot DOM suite pass; real API/BASE browser acceptance remains pending. Six other initial UI capabilities and all four progressive flows still require implementation/acceptance. Gates remain partial.

Increment after20Y: CLIENT_SUMMARY now has selected-customer UI, original CRM profile validation and passive observed/unavailable presentation. Build and targeted five-test DOM suite pass. Real signed SQLite API/official BASE browser suite6 passes desktop/tablet, including retained-policy identity, selected customer NEW classification, observed zero-ticket window, no phone, only query POST and unchanged policy. Both screenshots inspected; fixture cleaned/listeners0. Other seven initial UI capabilities and four progressive flows remain outstanding; all phase gates remain partial.

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
| COPILOT_READ | PARTIAL: scoped backend contracts exist for all12 names;20Y verifies four UI contracts | Eight remaining consultation/suggestion UI contracts and their current frontend/backend acceptance |
| COPILOT_SUGGEST | PARTIAL: deterministic rebooking/revenue/stock suggestions exist | Operator UI must preserve partial coverage, bounded counts and conditional assumptions without claiming money/contact/booking authority |
| COPILOT_PREPARE | PARTIAL: all4 progressive preparations exist in signed APIs | Operator UI must review exact selections/source digest and retained results, invalidate stale previews and handle uncertain acknowledgements/recovery per actor/institute |
| COPILOT_EXECUTE_GUARDED | PARTIAL: atomic explicitly approved CREATE/MOVE exist | Operator UI for separate prepare/decision/execute steps, fresh source checks and durable receipt/replay; marketing/reorder must stay within declared preparation-only scope |

At the20X baseline, `frontend/src/App.tsx` and `FlowPilotSidebar.tsx` had no general Copilot entry.20Y now adds that entry and four consultations, described below. `BaseCancellationPanel.tsx` still covers historical cancellation only; it does not prove CREATE/MOVE/marketing/reorder UI. Existing domain panels cannot substitute for proof that the Copilot interaction uses official BASE and these contracts. No phase closure is claimed from backend API tests or this partial UI alone.

## Initial consultation UI evidence (20Y)

The new `CopilotPanel.tsx` supports CLIENT_READ, PLANNING_READ, PLANNING_GAPS and STOCK_READ. Role-filtered server discovery is validated before modes are offered. Mode/question/customer start empty; selected customer comes from an explicitly requested owned search and service from the existing catalogue. Only explicit submit calls `/copilot/query`; no frontend language classifier or automatic domain consultation exists. API institute comes from signed auth; presentation also refuses an institute differing from token claims, without granting authority. Query carries message and explicit selections only, never contact/source records.

`copilot-read-utils.ts` checks closed envelope and source keys, exact selected customer/service, institute/capability/framework, capture/completion at microsecond precision, false history/booking/action boundaries and canonical evidence SHA before rendering. It reuses the existing outlook exact-quantity verifier with explicit pageSize50; existing callers keep default20. Editing clears facts; sequence checks and institute/token/timezone remount discard old results. The UI presents original planning reasons and unknown intervals, no inferred full work-hours/booking permission, exact stock versus pending/conditional shortfalls, first50 limit and capture clock. Customer search responses are reduced to ID/name; no phone displayed. No preparation/execution/contact controls are offered by this slice.

Build passes. Target DOM4 passed23.21s; full frontend528 passed90.91s, no failures/skips. Actual signed SQLite backend/official BASE browser suite final4 passed54.5s across desktop1440×900 and tablet1024×768; screenshots inspected, including correction of tablet numeric wrapping through horizontal table overflow. Tests exercise all four queries, exact selected identity/no phone, no implicit query/only query POSTs, unchanged stock, damaged-evidence refusal/restoration, manager-only403 and true unknown-route clarification. Earlier failures were browser locator/fixture assumptions, not weakened guards: four exact implicit-label locators changed to accessible role/name; the next two failures correctly exposed BASE routing the supposed unknown phrase to a manager-only capability, so the test now asserts403 and uses independently verified Bonjour clarification. Existing passlib/bcrypt and color-environment warnings remain. Owned browser fixture removed and loopback listeners4198/4199 confirmed0.

Remaining UI scope is CLIENT_SUMMARY, CLIENT_REBOOKING_OPPORTUNITIES, EMPLOYEE_CAPACITY, PLANNING_CONFLICTS (employee/resource), REVENUE_SUMMARY, REVENUE_LOSS_ANALYSIS, REVENUE_OPPORTUNITIES (capacity/rebooking/closures) and STOCK_FORECAST, then all four progressive preparations and separate exact CREATE/MOVE decision/execution/recovery. All four gates remain PARTIAL.20Y does not narrow the Master Plan's16 capabilities or prove whole-project production readiness.

## Current packaged backend evidence (20X)

The new image `sha256:92580c1c5b7a6b9b45e3e36a9ff06c9dd4acff4f2ca3dede8fcc868fcde2c470`, tag `flowpilot-copilot-20x-validation`, was built from backend/corpus baseline524c554 using `backend/Dockerfile`. Build validation passed29 BASE resources and54/54 lexical routing examples. Actual runtime versions are Python3.12.15 and Node22.23.3. This supersedes20K for current backend acceptance.

All19 `test_copilot*` modules, appointment creation/move domain preview modules20O/20R, marketing domain preview20U and reorder migration20W ran inside this actual Linux image:64 passed273.90s, zero failures/skips. Actual SQLite and isolated PostgreSQL16 were used; migration tests upgrade/preserve/compare schema and protect populated originals from downgrade. The single warning is the existing passlib crypt deprecation. Test/migration files were mounted read-only; this is not proof of a bundled production migration runner, whole-project acceptance, model quality or a deployed system. Language provider ports remain disabled; no external inference/contact/purchase was performed.

The PostgreSQL test server used a dedicated labelled Docker network and tmpfs data with no host port. After terminal successful completion, temporary fp_test schemas were0. Ownership labels were verified before removing only this server and its network; the test container removed itself. The image remains locally available. Logs are local `.cache/20x-build.log` and `.cache/20x-tests.log`.

UI work remains the next implementation task. Current packaged backend evidence does not close any of the four gates above by itself. Voice and later Master Plan phases remain incomplete; the full26-phase goal stays active.
