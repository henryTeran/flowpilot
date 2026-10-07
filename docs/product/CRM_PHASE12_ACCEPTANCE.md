# Phase 12 canonical acceptance audit

Authority: `FLOWPILOT_MASTER_PLAN.md` section 33, autonomous instructions and architecture foundations. This audit covers functional CRM acceptance on explicitly registered, institute-owned records. Physical-device, deployed runtime, delivery-provider and production-data acceptance are separate; they are not inferred from controlled fixtures.

## Requirement-to-evidence mapping

| Canonical requirement | Current implementation and executable evidence |
| --- | --- |
| NEW | Explicit registration-age threshold; `test_crm_segments_12c.py` six-state boundary cases; profile API and policy originals tests. |
| ACTIVE | Recorded paid-ticket evidence below declared loyalty threshold; same six-state cases. |
| LOYAL | Declared ticket-count threshold; boundary cases and owned profile source tests. |
| VIP | Declared count/currency/gross lower bound, no FX or missing-amount invention; six-state and uncertainty cases. |
| AT_RISK | Explicit inactivity threshold, priority and exact UTC recency; boundary cases. |
| DORMANT | Explicit longer inactivity threshold, registration/stale-read/unknown-source refusal; boundary cases. |
| Frequency | Whole observed paid-ticket cohort, exact rate per elapsed microsecond; metrics/billing tests stream 109 eligible tickets across batch boundary. Counts represent recorded tickets. |
| Recency | Exact capture-to-last recorded payment; absent evidence remains unavailable. Metrics/billing/profile tests and forged native profile refusal. |
| Average basket | Exact per-currency recorded gross/ticket ratio; explicit zero, missing/invalid amount diagnostics, no float or FX; metrics/billing/native tests. |
| CLV | Explicit finite remaining-lifetime constant-observed-rate scenario, declared duration/activity/margin/cost, exact rational result, scoped originals and native correction/recovery. Lifetime pure/original/API and native customer CRM tests. This is a conditional undiscounted scenario, not a calibrated prediction or historical net lifetime value. |
| Rebooking cycle | Completed session/appointment executions grouped into ticket care episodes; exact positive/zero gaps, overlapping-episode uncertainty; whole cohort and bounded source page. Return-cycle/source tests and native profile scenario. No inferred physical visits or employee booking credit. |
| Birthday automation | Explicit customer month/day and purpose-specific communication evidence; declared timezone/leap-day rule, local day bounds including DST; lifecycle/source/candidate/reconciliation tests and native calendar/declaration recovery. |
| Post-service automation | Actual owned completed care source; all observed care episodes yield explicit rule candidates. Source tests include 106 episodes; native event workflow creates actual completed care. |
| Rebooking automation | Latest recorded care completion plus explicit positive interval; unique occurrence identity and newer-source reconciliation. Candidate/reconciliation/source tests. |
| Inactivity automation | Latest recorded care completion plus explicit positive interval; uncertainty blocks action rather than inventing inactivity. Candidate/reconciliation/worker tests. |
| Package expiry automation | Owned explicit issued/expires term and remaining balance; anticipation clamps to issue, exhaustion/expiry/renewed-term identity. Source/candidate/reconciliation/ledger tests on SQLite/PostgreSQL. |
| Subscription renewal automation | Owned explicit active term; exact anticipation, expiry and renewed-term identity. Same six-trigger source/ledger coverage. |
| Durable automation execution | Atomic original/capture/revision/head ledger; source re-evaluation before internal processing; explicit revision-pinned cancellation, terminal processed/cancelled outcomes; worker batches <=20, bounded institute dispatch, explicitly enabled recurring runtime. Ledger/worker/dispatch/runtime tests, concurrent PostgreSQL cases and signed native event workflow. |
| Actor/scope/replay | Signed own-institute manager; exact literal original terms/actor, key-first replay and independently verified original/key/ID/current reads; malformed/foreign/stale refusal. Backend and frontend recovery tests plus signed browser reload scenarios. |
| Desktop/tablet UX | Native customer/profile, segment policy, birthday policy, lifecycle, automation rules and event workflows; controls >=44px, no horizontal overflow, source corruption hides stale facts. Edge desktop and touch-tablet projects. Physical hardware remains unverified. |
| Migration safety | Five CRM migrations plus recurring runtime schema preflight on isolated SQLite/PostgreSQL; scoped composite constraints, metadata comparison, protected retained-history downgrade refusal. No production migration applied by acceptance tests. |

## Interpretation and limits

Section 33 asks to calculate CLV and a rebooking cycle; it does not prescribe a learned CLV estimator, guaranteed complete historical data, physical visit inference, or campaign delivery. The implemented calculation exposes its explicit basis and suppresses unsupported results. These limitations do not create new canonical requirements. Marketing transports, campaigns and approve-before-send belong to Phase 13 (section 34); internal processing never claims external delivery authorization or message success.

The recurring runtime exists and is executable only with explicit institute/reason/cadence/state/token and migrated-schema preflight. Controlled execution/restart tests prove its behavior; no unattended production service is installed or certified.

## Current acceptance run

Full backend CRM (all 25 test files, including migrations, actual PostgreSQL enabled): 175 passed in 272.44s, zero failures/skips, terminal exit 0. Existing passlib crypt and Alembic path_separator deprecations only.
Combined signed native CRM browser suite (six specifications, desktop/touch-tablet): 12 passed in 2.2m, terminal exit 0; owned fixture removed. Launcher rebuilt before the suite. Existing nonfatal bcrypt-version/NO_COLOR warnings and WinError10054 from deliberate aborted replies observed.
Current full frontend baseline: 282 passed; TypeScript/Vite build passes at Phase 12AO. No whole-project backend rerun is claimed by this audit.

Functional gate verdicts after the completed runs and requirement-by-requirement coverage review:

- CRM_SEGMENTS = PASS: all six explicit states and recorded billing metrics.
- REBOOKING = PASS: source-supported recorded care cycle and latest-care automation.
- CUSTOMER_LIFECYCLE = PASS: registered customer metrics, declared conditional CLV and explicit birthday/communication lifecycle.
- AUTOMATION_EVENTS = PASS: all six source-supported triggers, durable atomic reconciliation/history/cancellation, bounded internal processing and explicitly enabled recurring runtime.

These are canonical Phase 12 functional verdicts. Physical hardware, production migrations/data/provider credentials, installed production worker and external delivery remain OPEN; no broader readiness is inferred. Proceed to Phase 13 Marketing. The full 26-phase goal remains ACTIVE.

## Reproducible acceptance scope

Backend command uses the already-running isolated validation runner and actual PostgreSQL fixture URL: `python -c "import glob,pytest; raise SystemExit(pytest.main(sorted(glob.glob('tests/test_crm_*.py'))+['-q','-p','no:cacheprovider']))"`. All 25 CRM test files are included, including migration and recurring schema preflight cases; fixture-owned schemas are disposable. This is not a production database run.

Native command from `frontend`: `npm run test:browser:backend -- backend-browser-tests/customer-crm.spec.ts backend-browser-tests/crm-policy-write.spec.ts backend-browser-tests/crm-lifecycle.spec.ts backend-browser-tests/crm-birthday-policy.spec.ts backend-browser-tests/crm-automation-policy.spec.ts backend-browser-tests/crm-events.spec.ts`. Both configured Edge projects run; signed fixture accounts and data are isolated and cleaned by the launcher. No external campaign or physical device was used.
