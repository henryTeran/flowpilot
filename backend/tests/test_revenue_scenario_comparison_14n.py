from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, localcontext
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
import app.main as main_module
from app.modules.revenue import scenario_comparison as comparison, scenario_originals as originals, sources
from app.modules.revenue.models import ScenarioOriginal
from app.modules.tickets.models import QueueTicket
from test_revenue_scenario_originals_14m import declaration
from test_revenue_scenarios_14d import request
from test_revenue_sources_14a import exercise
from test_revenue_billing_14a import NOW
from test_ticket_workflow import _bootstrap_reference_data, _auth_headers
from test_postgres_scheduling_4d import postgres_flow


def reference(envelope):
    return comparison.Reference(original_id=envelope.original["id"], fingerprint=envelope.fingerprint)


def retained(db, institute, key, assumptions=None):
    return originals.create(db, institute, declaration(key).model_copy(update={"assumptions": assumptions or request()}), "signed-manager")


def check(engine, institute, service, monkeypatch):
    exercise(engine, institute, service, monkeypatch)
    monkeypatch.setattr(originals, "utcnow", lambda: NOW)
    monkeypatch.setattr(comparison, "utcnow", lambda: NOW+timedelta(days=100))
    with Session(engine) as db:
        unavailable = retained(db, institute, "unavailable")
        db.delete(db.get(QueueTicket, "revenue-undated")); db.commit()
        baseline = retained(db, institute, "baseline")
        half_assumptions = request().model_copy(update={"activity_fraction": request().activity_fraction.model_copy(update={"denominator": "6"})})
        half = retained(db, institute, "half", half_assumptions)
        zero = retained(db, institute, "zero", request().model_copy(update={"activity_fraction": request().activity_fraction.model_copy(update={"numerator": "0"})}))
        monkeypatch.setattr(sources, "utcnow", lambda: NOW+timedelta(microseconds=1))
        clock_only = retained(db, institute, "clock-only", half_assumptions)
        db.get(QueueTicket, "revenue-00").total_amount = Decimal("2.01"); db.commit()
        changed = retained(db, institute, "changed-source")
        db.add(QueueTicket(id="comparison-eur", institute_id=institute, ticket_number="comparison-eur", arrival_time=NOW,
            status="paid", paid_at=NOW-timedelta(days=1), currency="EUR", total_amount=Decimal("3.03"))); db.commit()
        eur = retained(db, institute, "eur", request().model_copy(update={"currency": "EUR"}))
        observed = retained(db, institute, "short-observed", request().model_copy(update={"observed_start": NOW-timedelta(days=1)}))
        projected = retained(db, institute, "short-projected", request().model_copy(update={"projected_end": NOW+timedelta(days=3)}))
        payload = comparison.Request(baseline=reference(baseline), alternatives=tuple(reference(e) for e in
            (half, clock_only, changed, zero, unavailable, eur, observed, projected)))
        monkeypatch.setattr(sources, "read", lambda *a, **k: (_ for _ in ()).throw(AssertionError("Comparison recaptured mutable source")))
        with localcontext() as context:
            context.prec = 2
            result = comparison.read(db, institute, payload)
        assert result.selected_count == 9 and len(result.variants) == 9
        assert result.baseline_original_id == baseline.original["id"]
        assert result.summed_projected_gross_minor is None and not result.validated_prediction and not result.causal_effect_confirmed
        assert not result.action_executed and not result.full_institute_scenario_cohort
        base, lower, different_clock, different_source, explicit_zero, missing, foreign_currency, short_observed, short_projected = result.variants
        assert base.is_baseline and base.difference_from_baseline_minor.model_dump() == dict(numerator="0", denominator="1")
        assert lower.difference_from_baseline_minor.model_dump() == dict(numerator="-2525", denominator="4")
        assert lower.same_recorded_billing_aggregates and lower.same_source_capture
        assert different_clock.same_recorded_billing_aggregates and not different_clock.same_source_capture
        assert different_source.difference_from_baseline_minor.model_dump() == dict(numerator="50", denominator="1")
        assert not different_source.same_recorded_billing_aggregates and not different_source.same_source_capture
        assert explicit_zero.original.original["projected_gross_minor"] == dict(numerator="0", denominator="1")
        assert explicit_zero.difference_from_baseline_minor.model_dump() == dict(numerator="-2525", denominator="2")
        assert explicit_zero.difference_unavailable_reason is None
        assert missing.difference_from_baseline_minor is None and missing.difference_unavailable_reason == "unavailable_projection"
        assert foreign_currency.difference_from_baseline_minor is None and foreign_currency.difference_unavailable_reason == "currency_difference"
        assert short_observed.difference_unavailable_reason == "observed_period_difference"
        assert short_projected.difference_unavailable_reason == "projected_period_difference"
        assert [(c.currency, c.selected_count, c.valued_count, c.unavailable_count, c.summed_projected_gross_minor) for c in result.currencies] == [
            ("CHF", 8, 7, 1, None), ("EUR", 1, 1, 0, None)]
        for variant in result.variants:
            assert originals.fingerprint(variant.original.original) == variant.original.fingerprint
            assert variant.difference_basis == "comparison_only_not_attributed_effect"
        assert lower.original.original["projected_gross_minor"] == dict(numerator="2525", denominator="4")
        # A changed selection fingerprint and a malformed selected original both refuse the whole frame.
        wrong = payload.model_copy(update={"baseline": payload.baseline.model_copy(update={"fingerprint": "0"*64})})
        with pytest.raises(HTTPException): comparison.read(db, institute, wrong)
        duplicate = payload.model_copy(update={"alternatives": (payload.baseline,)})
        with pytest.raises(HTTPException): comparison.read(db, institute, duplicate)
        missing_baseline = comparison.Request(baseline=reference(unavailable), alternatives=(reference(baseline),))
        missing_frame = comparison.read(db, institute, missing_baseline)
        assert all(v.difference_from_baseline_minor is None and v.difference_unavailable_reason == "unavailable_projection" for v in missing_frame.variants)
        absent = payload.model_copy(update={"alternatives": (comparison.Reference(original_id="absent", fingerprint="0"*64),)})
        with pytest.raises(HTTPException) as error: comparison.read(db, institute, absent)
        assert error.value.status_code == 404
        row = db.get(ScenarioOriginal, projected.original["id"])
        raw = deepcopy(row.original); raw["projected_gross_minor"] = dict(numerator="999", denominator="1")
        row.original = raw; row.fingerprint = originals.fingerprint(raw); db.commit()
        tampered = payload.model_copy(update={"alternatives": (*payload.alternatives[:-1], comparison.Reference(original_id=row.id, fingerprint=row.fingerprint))})
        with pytest.raises(HTTPException): comparison.read(db, institute, tampered)
        db.rollback(); row.original = deepcopy(projected.original); row.fingerprint = projected.fingerprint; db.commit()
        assert db.scalar(select(func.count()).select_from(ScenarioOriginal)) == 9  # Read-only comparison.
        return payload, result


def test_sqlite_exact_retained_variant_comparison_and_signed_selection(client, monkeypatch):
    institute, _, services = _bootstrap_reference_data(client)
    payload, expected = check(main_module.engine, institute, services[0]["id"], monkeypatch)
    path = f"/api/v1/revenue/institutes/{institute}/scenarios/comparison"
    headers = _auth_headers("responsable_institut", institute)
    response = client.post(path, headers=headers, json=payload.model_dump(mode="json"))
    assert response.status_code == 200 and response.json() == expected.model_dump(mode="json")
    for role, owner in (("accueil", institute), ("collaboratrice", institute), ("responsable_institut", "foreign")):
        assert client.post(path, headers=_auth_headers(role, owner), json=payload.model_dump(mode="json")).status_code == 403
    assert client.post(path, json=payload.model_dump(mode="json")).status_code == 403
    for added in (dict(actor_id="injected"), dict(evidence={}), dict(projected_gross_minor="123")):
        assert client.post(path, headers=headers, json={**payload.model_dump(mode="json"), **added}).status_code == 422
    empty = payload.model_dump(mode="json"); empty["alternatives"] = []
    assert client.post(path, headers=headers, json=empty).status_code == 422
    many = payload.model_dump(mode="json"); many["alternatives"] = [dict(original_id=f"many-{n}", fingerprint="0"*64) for n in range(20)]
    assert client.post(path, headers=headers, json=many).status_code == 422
    wrong = payload.model_dump(mode="json"); wrong["baseline"]["original_id"] = " foreign "
    assert client.post(path, headers=headers, json=wrong).status_code == 422


def test_actual_postgres_exact_retained_variant_comparison(postgres_flow, monkeypatch):
    engine, institute, _, service = postgres_flow
    check(engine, institute, service, monkeypatch)
