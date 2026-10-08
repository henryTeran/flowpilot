"""Pure explicit-policy scoring of sovereign recorded-capacity alternatives.

Adapters must authenticate and derive the observations and policy. This module
neither trusts a public capacity payload nor treats a score as booking authority.
"""
from fractions import Fraction
from typing import Annotated, Literal
from pydantic import AwareDatetime, Field, StringConstraints, model_validator
from app.modules.waitlist import domain as matching
from app.modules.crm.metrics import Identifier

Factor = Literal["revenue_score", "utilization_score", "continuity_score",
    "client_preference_score", "employee_preference_score", "idle_gap_penalty",
    "overtime_penalty", "resource_conflict_penalty"]
FACTORS = ("revenue_score", "utilization_score", "continuity_score",
    "client_preference_score", "employee_preference_score", "idle_gap_penalty",
    "overtime_penalty", "resource_conflict_penalty")
PENALTIES = frozenset(FACTORS[5:])
CORE_CONSTRAINTS = (
    ("captured_demand_review", "source.demand", "Explicit human constraints review is confirmed"),
    ("captured_duration_match", "source.capture.service", "Declared and captured service durations agree"),
    ("captured_customer_window", "source.demand.availability", "Option fits declared customer availability and capture clock"),
    ("captured_employee_window", "source.capture.employees", "Option fits a known captured employee window and restriction"),
    ("captured_skills_match", "source.capture.service", "Captured employee qualification satisfies service requirements"),
    ("captured_distinct_resource_fit", "source.capture.resources", "Complete distinct captured resources fit without reservation conflicts"),
    ("captured_customer_conflicts", "source.capture.customer_blockers", "No captured customer occupation overlaps this option"),
    ("captured_queue_known", "source.capture.queue_capacity", "Core queue capacity is known and virtual blockers are applied"),
)
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=240)]
Unsigned = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]*)$", max_length=40)]
Positive = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$", max_length=40)]
Signed = Annotated[str, StringConstraints(pattern=r"^(0|-?[1-9][0-9]*)$", max_length=700)]
ScoreDenominator = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]*$", max_length=700)]


class Ratio(matching.Fact):
    numerator: Unsigned
    denominator: Positive

    def fraction(self):
        return Fraction(int(self.numerator), int(self.denominator))


class ExactScore(matching.Fact):
    numerator: Signed
    denominator: ScoreDenominator


def exact(value):
    return ExactScore(numerator=str(value.numerator), denominator=str(value.denominator))


class Weight(matching.Fact):
    factor: Factor
    value: Ratio


class Policy(matching.Fact):
    institute_id: Identifier
    id: Identifier
    captured_at: AwareDatetime
    reason: Text
    weights: tuple[Weight, ...] = Field(min_length=8, max_length=8)
    scale: Literal["explicit_normalized_unit_interval"] = "explicit_normalized_unit_interval"

    @model_validator(mode="after")
    def complete(self):
        if {row.factor for row in self.weights} != set(FACTORS):
            raise ValueError("Each official factor requires one explicit weight")
        if not any(row.value.fraction() for row in self.weights):
            raise ValueError("At least one factor must be explicitly weighted")
        return self


class Observation(matching.Fact):
    factor: Factor
    state: Literal["known", "unknown"]
    value: Ratio | None
    reference: Identifier | None
    observed_at: AwareDatetime | None
    reason: Text

    @model_validator(mode="after")
    def evidenced(self):
        if self.state == "known":
            if self.value is None or self.reference is None or self.observed_at is None:
                raise ValueError("Known normalized factor requires dated evidence")
            if self.value.fraction() > 1:
                raise ValueError("Normalized factor must lie in the unit interval")
        elif any(v is not None for v in (self.value, self.reference, self.observed_at)):
            raise ValueError("Unknown factor cannot fabricate a value or dated source")
        return self


class Constraint(matching.Fact):
    id: Identifier
    state: Literal["satisfied", "violated", "unknown"]
    reference: Identifier | None
    observed_at: AwareDatetime | None
    reason: Text

    @model_validator(mode="after")
    def evidenced(self):
        if self.state == "unknown":
            if self.reference is not None or self.observed_at is not None:
                raise ValueError("Unknown constraint cannot invent dated evidence")
        elif self.reference is None or self.observed_at is None:
            raise ValueError("Constraint conclusion requires dated evidence")
        return self


class Evidence(matching.Fact):
    option: matching.Option
    factors: tuple[Observation, ...] = Field(min_length=8, max_length=8)
    constraints: tuple[Constraint, ...]

    @model_validator(mode="after")
    def complete(self):
        if {row.factor for row in self.factors} != set(FACTORS):
            raise ValueError("Every factor must remain explicit, including unknowns")
        if len({row.id for row in self.constraints}) != len(self.constraints):
            raise ValueError("Constraint identities must be unique")
        if any(row.id == "observed_resource_conflict" or row.id.startswith("captured_") for row in self.constraints):
            raise ValueError("Reserved sovereign constraint identity")
        return self


class Contribution(matching.Fact):
    factor: Factor
    direction: Literal["reward", "penalty"]
    weight: Ratio
    observation: Observation
    state: Literal["included", "disabled_by_policy", "unavailable"]
    contribution: ExactScore | None


class ScoredOption(matching.Fact):
    option: matching.Option
    score: ExactScore | None
    rank: Annotated[int, Field(strict=True, ge=1)] | None
    state: Literal["conditional_scored", "score_unavailable", "constraint_blocked"]
    reasons: tuple[str, ...]
    constraints: tuple[Constraint, ...]
    contributions: tuple[Contribution, ...]


class Review(matching.Fact):
    institute_id: Identifier
    captured_at: AwareDatetime
    source: matching.Review
    policy: Policy
    options: tuple[ScoredOption, ...]
    ranking: Literal["complete", "incomplete_evidence", "no_admissible_options"]
    confidence: Literal["conditional_recorded_capacity_and_explicit_policy"] = "conditional_recorded_capacity_and_explicit_policy"
    action: Literal["human_review_then_revalidate_no_booking_or_contact"] = "human_review_then_revalidate_no_booking_or_contact"


def identity(option):
    return (option.start, option.end, option.employee_id, tuple(sorted(option.resource_ids)))


def score(source: matching.Review, policy: Policy, evidence: tuple[Evidence, ...]):
    """Recompute admissibility with the existing matching authority, then score.

    Missing weighted facts invalidate a complete ranking rather than becoming zero.
    Disabled factors preserve their unknown observations. Hard constraints cannot
    be traded away, including an observed resource conflict with a zero weight.
    """
    source = matching.Review.model_validate(source.model_dump())
    policy = Policy.model_validate(policy.model_dump())
    evidence = tuple(Evidence.model_validate(row.model_dump()) for row in evidence)
    verified = matching.match(source.demand, source.capture)
    if verified != source:
        raise ValueError("Scoring requires the complete sovereign matching result")
    clock = source.capture.captured_at
    if policy.institute_id != source.capture.institute_id or policy.captured_at > clock:
        raise ValueError("Explicit policy must share institute and captured chronology")
    options = {identity(row): row for row in source.options}
    if len(options) != len(source.options) or len({identity(row.option) for row in evidence}) != len(evidence) \
            or {identity(row.option) for row in evidence} != set(options):
        raise ValueError("Scoring evidence must exactly cover every captured alternative")
    weights = {row.factor: row.value for row in policy.weights}
    result, totals = [], {}
    for row in evidence:
        observations = {fact.factor: fact for fact in row.factors}
        constraints = [Constraint(id=key, state="satisfied", reference=path, observed_at=clock, reason=reason)
            for key, path, reason in CORE_CONSTRAINTS] + sorted(row.constraints, key=lambda c: c.id)
        for fact in (*row.factors, *row.constraints):
            if fact.observed_at is not None and fact.observed_at > clock:
                raise ValueError("Future evidence cannot support the captured score")
        conflict = observations["resource_conflict_penalty"]
        if conflict.state == "known" and conflict.value.fraction() > 0:
            constraints.append(Constraint(id="observed_resource_conflict", state="violated",
                reference=conflict.reference, observed_at=conflict.observed_at, reason="Observed resource conflict cannot be traded for score"))
        blocked = any(c.state != "satisfied" for c in constraints)
        total, unavailable, parts, reasons = Fraction(0), False, [], []
        for factor in FACTORS:
            observation, weight = observations[factor], weights[factor]
            coefficient = weight.fraction()
            direction = "penalty" if factor in PENALTIES else "reward"
            if coefficient == 0:
                state, value = "disabled_by_policy", None
                reasons.append(f"{factor}: explicitly disabled by policy; {observation.reason}")
            elif observation.state == "unknown":
                state, value, unavailable = "unavailable", None, True
                reasons.append(f"{factor}: weighted evidence unavailable; {observation.reason}")
            else:
                value = coefficient * observation.value.fraction() * (-1 if direction == "penalty" else 1)
                total += value
                state = "included"
                reasons.append(f"{factor}: {value.numerator}/{value.denominator}; {observation.reason}")
                value = exact(value)
            parts.append(Contribution(factor=factor, direction=direction, weight=weight,
                observation=observation, state=state, contribution=value))
        reasons.extend(f"constraint {c.id}: {c.state}; {c.reason}" for c in constraints)
        state = "constraint_blocked" if blocked else "score_unavailable" if unavailable else "conditional_scored"
        if state == "conditional_scored":
            totals[identity(row.option)] = total
        result.append(ScoredOption(option=options[identity(row.option)], score=exact(total) if state == "conditional_scored" else None,
            rank=None, state=state, reasons=tuple(reasons), constraints=tuple(constraints), contributions=tuple(parts)))
    ranking = "incomplete_evidence" if any(r.state == "score_unavailable" for r in result) else "complete" if totals else "no_admissible_options"
    # Sorting unknown/ineligible alternatives by source identity does not claim a score.
    scored = sorted((r for r in result if r.state == "conditional_scored"), key=lambda r: (-totals[identity(r.option)], identity(r.option)))
    if ranking == "complete":
        prior, rank = None, 0
        ranked = []
        for n, row in enumerate(scored, 1):
            value = totals[identity(row.option)]
            if prior is None or value != prior:
                rank = n
            prior = value
            ranked.append(row.model_copy(update={"rank": rank}))
        scored = ranked
    unscored = sorted((r for r in result if r.state != "conditional_scored"), key=lambda r: identity(r.option))
    ordered = sorted(result, key=lambda r: identity(r.option)) if ranking == "incomplete_evidence" else scored+unscored
    return Review(institute_id=policy.institute_id, captured_at=clock, source=source, policy=policy,
        options=tuple(ordered), ranking=ranking)
