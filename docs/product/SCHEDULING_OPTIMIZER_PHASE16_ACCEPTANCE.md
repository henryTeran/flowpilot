# Phase 16 — canonical acceptance audit

Authority: Master Plan section37 and relevant Definition of Done section64,
architecture foundations, implementation and actual test evidence. Starts from
clean implementation HEAD `50bca10`. The only code change in this audit is a native
test helper paging through policy history instead of assuming its selection is on
the first page. Product/backend/schema are unchanged. Full26-phase goal ACTIVE.

## Requirements and evidence

The canonical requirement is a deterministic engine returning option, score,
reasons and constraints. Its example names eight rewards/penalties; it does not
provide coefficients, a normalization policy, a catalog currency, a preference
taxonomy or physical working-hour evidence. Those are explicit assumptions or
unavailable facts, not quantities an assistant can invent to obtain a score.

| Requirement | Authoritative implementation and verification | Practical limit |
| --- | --- | --- |
| Deterministic engine | `optimizer/domain.py` revalidates the complete supplied matching result through the sovereign waitlist kernel, then uses exact Fraction arithmetic. `test_optimizer_domain_16a.py` proves weighted sums, negatives, permutations, exact ties, large denominators and refusal of forged/partial matching/evidence. | No alternate allocator, floating-point official score, stochastic model or scored fallback capacity. |
| Eight-factor formula | Exactly eight distinct explicit weights, reward/penalty direction and at least one enabled weight. `policy.py` validates each supported normalization basis;16A/B tests prove exact contribution signs, raw arithmetic, disabled/unknown behavior and hard resource conflict despite zero weight. | No arbitrary default coefficients. Disabled contribution is a deliberate policy choice, not measured zero. |
| Explicit policy/source |16C retains full rule terms/reasons/signed actor/server capture/key/raw JSON/SHA.16D selects ID/full fingerprint and latest matching event ID/full fingerprint under one institute lock/clock. Signed routes reject caller identity/clock/score/factors/capacity.16C/D tests cover actual SQLite/PostgreSQL source capture and refusal. | Policies are not global defaults. Historical policy retention is not an active booking/contact policy. |
| Option | Complete source-bound alternatives from existing matching/current capacity, not caller capacity.16D preserves matching policy refusal and current customer blocking;16G verifies full coverage;16H native review renders employee/times/resources. | Independent alternatives do not form a joint reservation plan or guarantee physical attendance/opening hours. |
| Score |16A exact reduced rational contributions/sums and competition ranks;16B explicit ceilings/raw normalization/saturation;16D derives elapsed duration/free-window ratio, start delay and captured distinct resource fit.16G rejects inconsistent numeric proof/rank/order;16H displays the exact server score. | Catalog currency, employee-linked continuity/preference indicators and declared working hours are unavailable in current source capture. Weighted unknowns make score/ranking unavailable; they are not guessed or silently ignored. |
| Reasons | Each contribution exposes weight, direction, evidence state, source reason and exact contribution. Constraint reasons and full raw normalization terms remain bound in the report.16G rejects altered reason strings;16H shows French known/unknown causes plus folded exact reasons/proofs. | Explanations describe recorded facts and explicit policy, not predicted revenue/profit or customer intent. |
| Constraints | Sovereign service duration, customer availability/review/blockers, employee windows/restrictions/skills, complete distinct resource fit and known queue capacity. Kernel supplemental unknown/violated constraints and known positive conflict block regardless of business score;16A/B tests prove this.16D currently supplies intrinsic constraints only;16G rejects unsupported arbitrary supplemental payloads. | Confirmed customer constraints are a declaration, not certification of every medical or physical rule. No unknown working-hour source becomes a satisfied overtime proof. |
| LLM boundary | All official arithmetic and source capture are deterministic Python services; current native review has no LLM dependency.16A/D API/kernel and16H exact-server-result assertions are the evidence. | Optional LLM explanation is not required by section37 and has not been added. No LLM official score or action authority. |
| Sensitive action audit | Policy originals record actor/reason/key/capture/full source terms/SHA; unique institute/key, scoped audited reads and whole-cohort validation before paging. Native16E/F freezes exact intent before I/O, verifies independent key/ID recovery and preserves unknown acknowledgement.16C races/rollback/recovery and16F native lost-response cases verify. | Scoring is read computation and executes no sensitive booking/contact action. SHA is consistency evidence, not SQL-admin authenticity or append-only triggers. |
| Permissions/tenant isolation | Signed manager/exact-institute routes, scoped retained policy/matching reads and current owned source capture;16C/D tests reject other roles/tenant/extra client-truth fields. Browser role/token/actor/scope/keyed-context guards suppress late results. | Controlled signed tests, not a new production penetration test. |
| Errors/recovery/concurrency | Strict aware horizons/rules/raw evidence; unknown/refused/malformed sources, stale fingerprints, changed head, future policy and invalid normalization refuse. Actual PostgreSQL same-key/conflicting requests serialize; flush rollback and committed lost acknowledgement recover.16C migrations guard retained-history/offline downgrade;16F/H mask failed/tampered replies and support explicit retry/reread. | No production failover, cross-tab locking or distributed-load certification. |
| UX/responsive | Empty policy defaults, explicit advanced authoring, lazy paged history, deliberate selection/current recapture, immediate context invalidation, readable French source causes, exact evidence folded, focus/scroll and44px controls.16F/H and fresh combined native tests cover signed desktop/touch-landscape profiles and no overflow. | Browser profiles, not physical tablet/portrait/mobile acceptance. Raw microseconds remain available in proof details. |
| Observability | Retained actor/key/capture/reason/fingerprint, source clocks/refusal diagnostics and complete score evidence. Existing structured API request logs/correlation remain in force. | Production telemetry/alerts/topology/incident exercises are separate gates. No retained audit of every read is claimed. |
| Documentation/commit/worktree | `SCHEDULING_OPTIMIZER.md`, this matrix and `PROJECT_STATUS.md` describe implementation, evidence, limits and next phase; coherent16A–H commits. | This audit is committed only after fresh verification, with final worktree check. Full objective is not declared complete. |

## Fresh verification

The frontend implementation is unchanged from `50bca10`: full frontend baseline
**487 passed83.90s**, no failures/skips/cancellations, terminalexit0, build186
modules.16F's eight policy and16H's six score/unknown/refusal captures were
individually inspected on this implementation. Fresh combined native runs
generate new captures and assert sizes/overflow; this audit does not claim manual
inspection of every newly generated capture.

Fresh backend command uses the dedicated owned validation runner/PostgreSQL,
SQLite in-memory/temporary DBs and fixture-owned random PostgreSQL schemas:

```text
pytest -p no:cacheprovider -q
  tests/test_optimizer_sources_16d.py
  tests/test_optimizer_originals_16c.py
  tests/test_optimizer_migration_16c.py
  tests/test_optimizer_policy_16b.py
  tests/test_optimizer_domain_16a.py
  tests/test_waitlist_sources_15d.py
  tests/test_waitlist_matching_15a.py
  tests/test_waitlist_detection_15e.py
  tests/test_waitlist_queue_15f.py
```

**73 passed144.16s**, zero failures/skips, terminalexit0. Includes actual PostgreSQL
policy replay/conflicting-request races, rollback/committed lost acknowledgement,
retained whole-cohort/off-page tamper, scoped signed API capture, unknown-factor
ranking guards, current blocker/refusal/corruption checks, migration metadata/
controlled roundtrip/history/offline guards and sovereign matching/detection/queue
regressions. Existing crypt deprecation and intentional unsafe-copy serializer
warning only. No persistent application database or provider was used.

Fresh combined native command:

```text
npm run test:browser:backend --
  backend-browser-tests/optimizer-policy-panel.spec.ts
  backend-browser-tests/optimizer-scoring-review.spec.ts
```

**4 passed1.2m**, zero failures/skips, terminalexit0; policy desktop11.4s,
score desktop10.0s, policy tablet11.8s, score tablet11.6s. One fresh signed Edge
harness rebuilt the current bundle/CSS, used owned temporary SQLite and confirmed
fixture cleanup. Policy/scoring fixtures coexist, requiring real pagination to
find a newly retained scoring policy beyond page1; the adjusted test helper uses
the existing native next-page action. Actual UI authoring/lost-response/reload
recovery, complete unique-ID history pagination, current server exact score,
unknown-weight no-ranking, permission refusal, altered proof mask/retry,
peer-revision400/reread, full fingerprints/strict request shape/context edits and
no UI booking/contact/policy writes during score review all pass. Extra originals,
initial customers/demands/activations and peer revisions are API test fixtures,
not additional native authoring claims. Existing bcrypt/NO_COLOR warnings only.

## Gate decision

SCHEDULING_OPTIMIZER, SCORING_DETERMINISTIC and EXPLANATION_EVIDENCE = **PASS at
controlled local functional scope**. Each canonical section37 output and relevant
section64 criterion maps to implementation and scoped evidence above. There is
no claim that all real-world scoring inputs are known, a policy is an approved
economic model, or alternatives are physically available. Missing facts remain
explicitly unavailable; configured unknown weights prevent complete scores.
This is Phase16 acceptance, not completion of the entire Master Plan.

Production/topology/persistent migration, live providers, physical device/real
occupation validation, large-cohort/load and fresh whole-project acceptance remain
OPEN. Headb128ef60a9d2 is an application deployment prerequisite; it was tested
only in owned temporary databases and has not been applied to the persistent
application/production database. No provider message, booking, deployment or push
is performed by this checkpoint. Next canonical phase:17 BASE Foundation.
