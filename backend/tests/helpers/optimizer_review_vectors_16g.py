"""Current adapter/kernel DTO vectors from typed matching fixtures, without SQL."""
import json
import sys
from pathlib import Path
from datetime import timedelta
from app.modules.optimizer import sources, originals, policy, domain
from app.modules.waitlist import sources as matching

fixture = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
result = {}
cases = [("options", "options", {"utilization_score"}), ("delay", "options", {"idle_gap_penalty"}),
    ("duration_changed", "duration_changed", {"utilization_score"}), ("queue_unknown", "queue_unknown", {"utilization_score"}),
    ("permission_refused", "permission_refused", {"utilization_score"}), ("cancelled", "cancelled", {"utilization_score"}),
    ("queue_known", "queue_known", {"utilization_score"})]
cases += [(f, "options", {f}) for f in sources.UNKNOWN]
cases += [("multiple", "options", {"utilization_score"}), ("multiple_tie", "options", {"utilization_score"})]
for name, source_name, enabled in cases:
    source = matching.Read.model_validate(fixture[source_name])
    if name.startswith("multiple"):
        start = source.review.demand.availability[0].start
        split = start+timedelta(minutes=30)
        employee = source.review.capture.employees[0].model_copy(update={"windows": (
            domain.matching.Window(start=start-timedelta(minutes=10 if name == "multiple" else 0), end=split),
            domain.matching.Window(start=split, end=start+timedelta(hours=1)))})
        capture = source.review.capture.model_copy(update={"employees": (employee,)})
        source = source.model_copy(update={"review": domain.matching.match(source.review.demand, capture)})
    rules = tuple(policy.Rule(factor=f, weight=domain.Ratio(numerator="1" if f in enabled else "0", denominator="1"),
        basis=policy.BASES[f] if f in enabled else "disabled",
        ceiling="10000" if f in enabled and f == "revenue_score" else "60000000" if f in enabled and f in {"idle_gap_penalty", "overtime_penalty"} else None,
        currency="CHF" if f in enabled and f == "revenue_score" else None, price_mode="member" if f in enabled and f == "revenue_score" else None,
        reason="Explicit scoring assumption reviewed") for f in domain.FACTORS)
    original = originals.Original(terms=policy.Terms(rules=rules), reason="Explicit policy for current review",
        idempotency_key=name, id=f"optimizer_policy_{name}", institute_id="own", actor_id="manager",
        created_at=source.captured_at-timedelta(minutes=1))
    raw = original.model_dump(mode="json")
    envelope = originals.Envelope(original=raw, fingerprint=originals.fingerprint(raw))
    proofs = sources.derive(source, original.terms)
    review = None
    catalog = None
    if source.review is not None:
        catalog = sources.Catalog(service_id=source.review.demand.service_id, price_member="29.90", price_passage=None)
        review = domain.score(source.review, policy.scoring_policy(original.terms, "own", original.id, original.created_at, original.reason),
            tuple(domain.Evidence(option=p.option, factors=tuple(f.observation for f in p.factors), constraints=()) for p in proofs))
    result[name] = sources.Read(institute_id="own", captured_at=source.captured_at, policy_original=envelope,
        source=source, catalog=catalog, proofs=proofs, review=review).model_dump(mode="json")
Path(sys.argv[2]).write_text(json.dumps(result, ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
