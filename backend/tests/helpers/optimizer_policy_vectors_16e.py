"""Typed backend originals/SHA vectors; no SQL connection or application startup."""
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from app.modules.optimizer import originals, policy, domain

now = datetime(2026, 10, 8, 11, tzinfo=timezone.utc)
rules = tuple(policy.Rule(factor=f, weight=domain.Ratio(numerator="1" if f == "utilization_score" else "0", denominator="1"),
    basis=policy.BASES[f] if f == "utilization_score" else "disabled", ceiling=None, currency=None, price_mode=None,
    reason="Explicit normalization reviewed") for f in domain.FACTORS)
terms = policy.Terms(rules=rules)
rows = []
for n in range(25):
    original = originals.Original(terms=terms, reason="Explicit policy reviewed \u2014 no default activation",
        idempotency_key=f"policy-{n}", id=f"optimizer_policy_{n:03d}", institute_id="own", actor_id="signed-manager",
        created_at=now+timedelta(microseconds=n)).model_dump(mode="json")
    rows.append(originals.Envelope(original=original, fingerprint=originals.fingerprint(original)))
result = {str(offset): originals.Audit(institute_id="own", captured_at=now+timedelta(minutes=1), offset=offset,
    limit=20, total=25, originals=rows[offset:offset+20]).model_dump(mode="json") for offset in (0, 20, 40)}
Path(sys.argv[1]).write_text(json.dumps(result, ensure_ascii=True, indent=2)+"\n", encoding="utf-8")
