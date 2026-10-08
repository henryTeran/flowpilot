# Scheduling Optimizer — Phase16

Authority: Master Plan section37. SCHEDULING_OPTIMIZER, SCORING_DETERMINISTIC and
EXPLANATION_EVIDENCE remain OPEN until authenticated source/policy integration,
native review and scoped end-to-end acceptance.16A supplies the pure deterministic
kernel;16B adds explicit normalization terms and raw-to-normalized proof. The
full26-phase objective remains ACTIVE.16C adds retained signed policy originals;
16D adds authenticated current factor capture. Native optimizer review remains
unfinished.

## Official calculation

`app/modules/optimizer/domain.py` recomputes the supplied complete matching result
with the existing sovereign `waitlist.domain.match` before scoring any alternative.
An injected option, partial option cohort or forged matching reason refuses.
The module does not duplicate qualification/resource allocation, query SQL, book,
reserve, contact, or give an LLM control of official arithmetic.

All eight canonical factors are explicit:

| Factor | Sign | Required interpretation |
| --- | --- | --- |
| revenue_score | Reward | Evidenced normalized conditional reference value; never fabricated price, profit or causal uplift |
| utilization_score | Reward | Evidenced normalized recorded capacity measure under an explicit basis |
| continuity_score | Reward | Evidenced continuity measure under an explicit rule; absence of source stays unknown |
| client_preference_score | Reward | Explicit retained preference under a declared rule; not inferred intention |
| employee_preference_score | Reward | Explicit retained preference under a declared rule; not inferred willingness |
| idle_gap_penalty | Penalty | Evidenced normalized recorded gap under an explicit window/basis |
| overtime_penalty | Penalty | Evidenced overtime rule/context; not invented working hours |
| resource_conflict_penalty | Penalty and hard guard | Observed resource conflict blocks regardless of its weight; resource safety cannot be bought by revenue |

The example in section37 does not authorize default business coefficients or
missing-source guesses. Policy has one explicit nonnegative rational weight per
factor, institute, identity, capture and reason, with at least one nonzero weight.
Each observation is either known with a dated source reference, reason and exact
unit-interval ratio, or explicitly unknown with no numeric value/reference/clock.
Input ratios are decimal integer strings, not floats. Positive denominators and
bounded input lengths retain exact `Fraction` arithmetic. Signed scores and
contributions are reduced rational strings; output bounds cover the full eight-
factor input arithmetic, including denominators longer than40 digits.

For an enabled known factor, contribution = weight × normalized value, negated
for a penalty. Disabled factors retain their observed/unknown state and have no
claimed measured contribution; zero policy weight is not a measured zero. Any
unknown enabled factor prevents a complete ranking. Known scores remain inspectable,
but all ranks are absent and the entire report sorts by source identity rather
than displaying a partial “best” ahead of an unknown alternative.

With complete evidence, eligible alternatives sort by descending exact score,
then UTC start/end, employee identity and sorted resource identities. Equal scores
have equal competition rank; the deterministic display tie-break is not a customer
preference. Negative scores are legal. Input evidence/factor/weight permutations
do not change official scores, explanations or ranks.

## Constraints and explanation

Each returned option exposes score, rank/state, all eight weighted contributions,
source-linked reasons and constraints. Eight intrinsic constraints refer into the
included verified matching snapshot: human demand review, duration, customer window,
employee window/restriction, skills, distinct resource fit, customer blockers and
known core queue projection. They describe recorded conditional admissibility,
not physical execution or opening-hours verification.

Additional explicit constraints require dated evidence for satisfied/violated
conclusions. Unknown or violated constraints block an option and suppress its
official score/rank, irrespective of rewards or penalties. Intrinsic constraint
identities are reserved and cannot be overridden. Positive observed resource
conflict adds a hard violated constraint even when its weight is zero. An unavailable
core matching result remains empty; no fallback capacity or scored reservation is
invented. Report action remains human review and revalidation, with no booking/contact.

## Source and integration boundary

The pure kernel accepts typed observations; it does not authenticate caller-supplied
references, establish policy approval or derive a normalized value from SQL. No
public endpoint accepts these precomputed observations. Source adapters must bind
signed institute/actor, current selected source version, server capture, complete
alternatives, retained explicit policy and dated evidence/normalization. They must
preserve current matching history/permission refusal, not bypass it by extracting
only a capacity snapshot. Missing prices, working hours, preferences or continuity
sources remain unknown unless an explicit policy disables that factor; unknown hard
constraints still block. A score is neither an agreed quote nor contact authority.

Next work includes retained scoped policy/normalization originals and key recovery,
sovereign current source capture and factor derivation, signed version-pinned review,
native factor/score/risk inspection, source invalidation and canonical acceptance.
SQL migrations, production/topology/load/provider/physical gates remain separate.

## 16A verification

Initial combined optimizer/existing matching27 passed0.57s. Expanded rational-size
boundary vector failed its expected-length assertion because symmetric terms
canceled exactly; changed the independent denominators, not the official formula.
Added explicit intrinsic constraint proofs/reserved-identity protection. Final
combined **28 passed0.52s**, zero failures/skips, terminalexit0:16 optimizer cases and
12 existing matching cases. Covers exact rewards/penalties and large fractions,
unknown/disabled distinctions, complete versus incomplete rankings, negative scores,
ties/permutations, unknown/violated hard constraints and zero-weight resource conflict,
scope/future-clock rejection, forged/partial alternatives, malformed ratio/evidence,
unsafe model-copy revalidation and unavailable core matching.

Existing Starlette/httpx deprecation and one intentional unsafe-copy Pydantic warning.
No SQL/API/native/current-source acceptance is claimed by these pure-kernel tests.
Existing API services/routes/schema/frontend unchanged; no persistent migration/provider/deployment.
All three Phase16 gates remain OPEN and the full objective stays ACTIVE.

## 16B explicit normalization terms

`optimizer/policy.py` defines a complete eight-rule policy contract. Every rule
has a factor, exact weight, supported basis and explicit reason. Zero weights
require a disabled basis and no hidden ceiling/currency/mode. Enabled catalog
reference requires a positive minor-unit ceiling, currency and member/passage
mode. Elapsed gap/overtime penalties require explicit microsecond ceilings.
Utilization is proposed elapsed duration over its complete containing free window;
continuity/preferences/conflicts require exact recorded binary indicators. No
numeric default, inferred working hours, inferred preference or guessed tariff
is introduced. These are declared score assumptions, not verified business impact.

Raw source quantities retain basis, quantity/denominator, monetary dimensions,
reference, observed clock and reason. Missing quantity has no fabricated numeric
terms or dated reference. Wrong factor/basis/currency/mode, future evidence,
malformed binary/interval and unsafe copied policy refuse. Normalization uses
exact fractions, explicitly caps quantities above a declared ceiling at one,
and exposes the saturation flag plus original raw quantity/ceiling. It neither
rewrites a reference price nor turns it into a quote, profit or prediction.
Disabled factors retain raw trace without claiming a normalized zero. Known
resource conflict remains a known indicator even with a disabled scoring weight,
so the16A hard rule still blocks it. Complete terms convert to canonical factor
weights for the existing scorer.

Final combined normalization/scoring/existing matching **47 passed0.70s**, zero
failures/skips, terminalexit0 (19 normalization,16 scoring,12 matching cases).
Covers all eight unavailable-source cases, exact ratios/elapsed units/saturation,
explicit monetary/disabled terms, currency/mode/future rejection, duplicate/empty
policy, unsafe-copy revalidation and disabled-weight hard-conflict propagation.
Existing Starlette/httpx and intentional unsafe-copy warnings only. No SQL/API/
native source authentication or retained-policy claim yet; these contracts are
not a public client-supplied scoring endpoint. Existing services/routes/schema/
frontend unchanged. Next: retained scoped normalization/weight originals with
signed actor, source hash, key recovery and controlled migrations; then actual
current factor capture and version-bound native review. All Phase16 gates OPEN.

## 16C retained signed policy originals

`optimizer/originals.py` and signed manager/exact-institute routes retain the full
eight-rule terms, reason, idempotency key, server identity/actor/capture and raw
JSON/SHA. The client cannot inject identity, scope, actor, capture or score. Policies
are independent retained scoring assumptions: creation does not activate a global
default, grant booking/contact authority or compute an official score. A score
review must explicitly select its retained original and fingerprint later.

Every read verifies the full raw fingerprint, strict typed snapshot/canonical
representation, logical normalization rules, row identity/scope/actor/key/clock and
nonfuture capture. Raw rehashed malformed claims, noncanonical trimmed terms and
column contradictions refuse. Integrity is consistency evidence, not SQL-admin
authenticity or an append-only-trigger claim. Key replay binds the exact retained
request and actor; changed terms/reason/actor cannot reuse it. Scoped key/ID reads
recover a committed acknowledgement without another original. Institute locking
and SQL unique institute/key constraints serialize actual PostgreSQL races.
Failures roll back; no policy is retained after failed flush.

POST `/optimizer/institutes/{institute}/policy-originals` accepts only terms/reason/
key. GET policy-original-by-key, GET policy-originals/{id}, and explicit20-row GET
policy-originals history require the same signed manager scope. Whole retained
cohort verifies before pagination, so corruption outside a requested page cannot
hide behind counts. The history is not an active operational policy head.

Migration `b128ef60a9d2` follows `a017d865bb4c` and registers matching runtime/Alembic
metadata. Empty temporary SQLite/PostgreSQL down/up and metadata comparisons are
tested; offline downgrade and removal with retained history refuse. No persistent
application or production database is migrated by this checkpoint.

Final complete eight-module regression70 passed66.82s, zero failures/skips, terminalexit0, with SQLite and actual isolated PostgreSQL. Includes actual same-key/conflicting-request races, rollback/lost acknowledgement, signed scope/injection rejection,25-row20/5 history/off-page tamper, canonical raw-proof checks, controlled migration roundtrips/metadata/history guards, and existing scoring/normalization/matching/original/migration compatibility.

Initial eight-module run69 passed/1 failed83.77s: test assumed absence for an
institute that did not exist, while the existing institute guard correctly returned
404. Added an owned foreign institute; next69 passed/1 failed70.87s exposed its
missing required city field. Completed the fixture without weakening production
guards. Strengthened canonical raw-snapshot verification and rehashed whitespace
tamper coverage. Existing crypt deprecation and intentional unsafe-copy serializer
warnings are separate from test failures.

No frontend/native optimizer or whole-project/production acceptance claimed.

## Current source derivation (16D)

POST `/optimizer/institutes/{institute}/reviews/current` is a read computation,
not a retained write. Its strict body names selected policy ID/full fingerprint,
waitlist root/latest event ID/full fingerprint, explicit aware horizon and the
existing matching policy. Signed manager/exact-institute authorization applies.
It accepts no caller clock, observations, weights, scores or capacity payloads.
The institute lock, verified retained policy and existing matching reader share
one server clock. A changed matching head or policy fingerprint refuses the read.
Matching policy refusal is preserved with its complete source and no score,
catalog or option proofs. No alternative allocator or fallback availability runs.

For every sovereign option, the response preserves its complete matching source,
selected policy original and eight raw-to-normalized factor proofs. Utilization
uses exact proposed elapsed microseconds divided by the complete containing
captured employee free-window microseconds; the window is included per option.
This is a conditional fill ratio, not institute or physical utilization. Delay
uses option start minus capture in elapsed microseconds, not measured employee
idle time. Distinct resource fit from sovereign matching supplies a zero current
conflict indicator. Its proof remains active even if its business weight is zero;
it cannot predict future conflicts or authorize booking.

All five remaining factors explicitly remain unknown: catalog currency is absent
(both recorded member/passage prices are retained as conditional references),
care history has no employee-linked continuity indicator, availability/employee
restrictions are hard constraints rather than graded client preferences, no
employee preference indicator exists, and declared working hours are unavailable
for overtime measurement. Neither a selected currency nor a missing price,
history, preference or working-hour record is converted to a measured zero.
Enabling any unavailable factor prevents a complete ranking. Explicit zero
weights disable its contribution while preserving the unavailable source.
Ceiling saturation keeps the original elapsed quantity and chosen ceiling.

The kernel returns option, exact score, reasons and constraint evidence; all
reads require human review and fresh booking/contact validation. No LLM computes
official scores. No schema change beyond16C headb128ef60a9d2, persistent
application migration, provider action or deployment is part of16D.

Validation: initial five-module51 passed34.75s. Expanded nine-module72pass/1fail
103.12s found a fixture using a resource status already rejected by SQL CHECK;
the fixture now uses malformed JSON capabilities without weakening the schema.
Final complete nine-module **73 passed87.48s**, zero failures/skips, terminalexit0,
with SQLite and actual isolated PostgreSQL. Covers current scoring/proofs and
repeated reads, source/policy fingerprint pinning, dynamic customer occupation,
permission refusal, each unavailable weighted factor, elapsed saturation,
expired horizon/future policy/current source corruption, signed authorization and
client-truth injection rejection, plus retained policy/migration/kernel/
normalization and existing matching/current capture/detection/queue regressions.
Native/frontend and whole-project acceptance are not claimed by this backend
integration.

## Browser policy contracts and recovery (16E)

`optimizer-policy-utils.ts` validates exactly eight distinct explicit rules and
all normalization dimensions. Decimal weights/ceilings remain canonical strings
with the same40-digit bounds as the backend; no floating-point comparison or
implicit default weight is introduced. Disabled rules require disabled basis and
null normalization parameters; monetary/elapsed/ratio rules require their own
dimensions. Requests reject extra actor/scope/score fields. Retained originals
verify full raw SHA, canonical UTC capture, signed actor/scope and no-action
marker. Audits verify20-row cardinality, clock/order, unique identity/key and each
full original. Backend whole-cohort verification remains the authority for
off-page records. Neither browser verification nor SHA certifies SQL-admin
authenticity.

`optimizer-policy-intent.ts` retains exact request/actor/institute before reads or
writes. Only literal null recovery authorizes a POST. Confirmation requires exact
ordered request rules, actor and independently consistent full-SHA key/ID reads
before clearing saved state. Unknown acknowledgement or failed verification keeps
the frozen intent across reload. A definitive POST400/404/422 can offer correction
only after a fresh null key read; intervening originals recover instead. Invalid
storage, persistence failure, changed storage, concurrent same-scope instances
and stale authority block or preserve state. No policy activates as a default.

Fixtures come from the actual Python Original/Terms/Audit and SHA models through
`backend/tests/helpers/optimizer_policy_vectors_16e.py`, without SQL or application
startup. They include25 microsecond-dated originals/Unicode reason and20/5/empty
pages. Fifteen focused contract/recovery tests passed594.18ms, zero failures/skips,
terminalexit0; TypeScript/Vite build passed181 modules. Initial test-file
generation used the wrong working path, so that preliminary run covered only the
five contract cases; corrected generation and final focused run include all ten
recovery cases. Complete frontend **472 passed83.83s**, zero failures/skips,
terminalexit0. Backend runtime is unchanged;16D backend evidence remains separate.

These modules are not yet imported by the product UI. No native policy
authoring/history/score review or complete Phase16 gate acceptance is claimed.
SCHEDULING_OPTIMIZER / SCORING_DETERMINISTIC / EXPLANATION_EVIDENCE remain OPEN.
Next: sovereign factor derivation from current matching/SQL sources, selected
retained policy/full fingerprint, raw normalization proof and version-pinned signed
review; then native policy authoring/history/recovery and score/reason/risk review.
