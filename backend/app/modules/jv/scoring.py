"""Explain sovereign optimizer scores without inventing weights or eligibility."""
from typing import Literal
from app.modules.crm.metrics import Fact
from app.modules.base.read_capabilities import Digest, ExactId
from app.modules.optimizer import sources, originals, policy, domain
from app.modules.jv.operational import Citation
from app.modules.waitlist.originals import fingerprint


class Alternative(Fact):
    option: domain.matching.Option
    score: domain.ExactScore | None
    rank: int | None
    state: Literal["conditional_scored", "score_unavailable", "constraint_blocked"]
    reasons: tuple[str, ...]
    contributions: tuple[domain.Contribution, ...]
    constraints: tuple[domain.Constraint, ...]
    sources: tuple[Citation, ...]


class ScoringAnalysis(Fact):
    institute_id: ExactId
    evidence_fingerprint: Digest
    policy_fingerprint: Digest
    rule_version: Literal["jv.optimizer_explanation.v1"] = "jv.optimizer_explanation.v1"
    ranking: Literal["complete", "incomplete_evidence", "no_admissible_options", "source_unavailable"]
    unavailable_reason: str | None
    alternatives: tuple[Alternative, ...]
    actions: tuple[()] = ()
    meaning: Literal["conditional_comparison_not_profit_prediction_or_booking_authority"] = "conditional_comparison_not_profit_prediction_or_booking_authority"
    fingerprint: Digest


def analyze(candidate: sources.Read) -> ScoringAnalysis:
    source = sources.Read.model_validate(candidate.model_dump(mode="json"))
    original = originals.Original.model_validate(source.policy_original.original)
    if fingerprint(source.policy_original.original) != source.policy_original.fingerprint:
        raise ValueError("JV optimizer policy digest mismatch")
    if original.institute_id != source.institute_id or original.created_at > source.captured_at or source.source.captured_at != source.captured_at:
        raise ValueError("JV optimizer scope/chronology mismatch")
    for envelope in (source.source.state.root, source.source.state.current_demand, *source.source.state.events):
        if envelope.original.get("institute_id") != source.institute_id or fingerprint(envelope.original) != envelope.fingerprint:
            raise ValueError("JV optimizer demand original mismatch")
    if (source.source.review is None) != (source.source.unavailable_reason is not None):
        raise ValueError("JV optimizer source availability mismatch")
    proofs = sources.derive(source.source, original.terms)
    if proofs != source.proofs:
        raise ValueError("JV optimizer normalization proof mismatch")
    review = None
    if source.source.review is not None:
        review = domain.score(source.source.review,
            policy.scoring_policy(original.terms, source.institute_id, original.id, original.created_at, original.reason),
            tuple(domain.Evidence(option=p.option, factors=tuple(f.observation for f in p.factors), constraints=()) for p in proofs))
    if review != source.review:
        raise ValueError("JV optimizer scoring proof mismatch")
    digest = fingerprint(source.model_dump(mode="json"))
    alternatives = tuple(Alternative(option=row.option, score=row.score, rank=row.rank, state=row.state,
        reasons=row.reasons, contributions=row.contributions, constraints=row.constraints,
        sources=(Citation(evidence_fingerprint=digest, pointer=f"/review/options/{index}"),))
        for index, row in enumerate(review.options)) if review else ()
    result = ScoringAnalysis(institute_id=source.institute_id, evidence_fingerprint=digest,
        policy_fingerprint=source.policy_original.fingerprint,
        ranking=review.ranking if review else "source_unavailable", unavailable_reason=source.source.unavailable_reason,
        alternatives=alternatives, fingerprint="0" * 64)
    return result.model_copy(update={"fingerprint": fingerprint(result.model_dump(mode="json", exclude={"fingerprint"}))})


class Response(Fact):
    source: sources.Read
    analysis: ScoringAnalysis
