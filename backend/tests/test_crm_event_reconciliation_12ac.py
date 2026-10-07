from datetime import timedelta
import pytest
from app.modules.crm.event_reconciliation import identity, reconcile
from app.modules.crm.event_sources import EventSourceRead
from app.modules.crm.lifecycle_originals import LifecycleRead
from test_crm_event_candidates_12z import fixture, clock

def snapshot():
    from app.modules.crm.event_candidates import candidates
    p,c,s=fixture()
    life=LifecycleRead(institute_id="i",customer_id="c",captured_at=clock(7),customer=c,
        original=None,calendar_original=None,birthday=None,unavailable_reason="declaration_absent")
    # Pure reconciliation consumes already-captured candidates; source API tests
    # separately prove selected originals and registered-source capture.
    return EventSourceRead(institute_id="i",customer_id="c",captured_at=clock(7),customer=c,
        policy_original=None,lifecycle=life,anchors=s,candidates=candidates(p,"original",c,clock(7),s),diagnostics={})

def test_repeated_capture_policy_and_care_clock_corrections_do_not_duplicate_occurrences():
    capture=snapshot();first=reconcile(capture,())
    assert len(first)==6 and reconcile(capture,first)==first
    changed=tuple(v.model_copy(update={"policy_original_id":"corrected"}) for v in capture.candidates)
    second=reconcile(capture.model_copy(update={"candidates":changed}),first)
    assert {v.event_key for v in second}=={v.event_key for v in first}
    care=next(c for c in capture.candidates if c.rule.trigger=="post_service")
    assert identity(care)==identity(care.model_copy(update={"source":care.source.model_copy(update={"occurred_at":clock(6)})}))
    membership=next(c for c in capture.candidates if c.rule.trigger=="subscription_renewal")
    assert identity(membership)!=identity(membership.model_copy(update={"source":membership.source.model_copy(update={"expires_at":clock(9)})}))

def test_uncertain_absence_blocks_and_explicit_cancellation_or_processed_events_stay_terminal():
    capture=snapshot();first=reconcile(capture,())
    absent=capture.model_copy(update={"candidates":()})
    assert all(v.state=="blocked" and v.reason=="source_uncertain" for v in reconcile(absent,first))
    cancelled=first[0].model_copy(update={"state":"cancelled","reason":"explicit_cancellation"})
    processed=first[1].model_copy(update={"state":"processed","reason":"already_processed"})
    result=reconcile(capture,(cancelled,processed)+first[2:])
    assert cancelled in result and processed in result

def test_disabled_exhausted_expired_and_superseded_terms_remain_distinct():
    capture=snapshot();first=reconcile(capture,())
    updated=[]
    for c in capture.candidates:
        state={"birthday":"expired","post_service":"disabled","package_expiry":"exhausted"}.get(c.rule.trigger,c.state)
        updated.append(c.model_copy(update={"state":state}))
    result=reconcile(capture.model_copy(update={"candidates":tuple(updated)}),first)
    reasons={v.candidate.rule.trigger:v.reason for v in result}
    assert reasons["birthday"]=="occurrence_expired" and reasons["post_service"]=="rule_disabled" and reasons["package_expiry"]=="package_exhausted"
    latest=tuple(c.model_copy(update={"source":c.source.model_copy(update={"source_id":"latest"})}) if c.rule.trigger=="inactivity" else c for c in capture.candidates)
    replaced=reconcile(capture.model_copy(update={"candidates":latest}),first)
    assert len(replaced)==7 and any(v.reason=="superseded" for v in replaced)

def test_foreign_duplicate_or_backward_events_and_foreign_fresh_sources_fail():
    capture=snapshot();first=reconcile(capture,())
    for previous in (first+(first[0],), (first[0].model_copy(update={"event_key":"wrong"}),),
                     (first[0].model_copy(update={"evaluated_at":clock(7)+timedelta(microseconds=1)}),)):
        with pytest.raises(ValueError): reconcile(capture,previous)
    foreign=capture.candidates[0].model_copy(update={"customer_id":"foreign"})
    with pytest.raises(ValueError): reconcile(capture.model_copy(update={"candidates":(foreign,)}),())
