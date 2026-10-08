# Scheduling Optimizer — Phase16

Authority: Master Plan section37. SCHEDULING_OPTIMIZER, SCORING_DETERMINISTIC and
EXPLANATION_EVIDENCE remain OPEN until authenticated source/policy integration,
native review and scoped end-to-end acceptance.16A supplies the pure deterministic
kernel; the full26-phase objective remains ACTIVE.

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
