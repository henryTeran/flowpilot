from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from app.modules.crm.automation_policy import AutomationPolicy
from app.modules.crm.event_candidates import EventAnchor, candidates
from app.modules.crm.segments import RegisteredCustomerFact

def clock(day):
    return datetime(2026, 10, day, tzinfo=timezone.utc)

def fixture():
    policy = AutomationPolicy(institute_id="i",rules=tuple({"trigger": t,"enabled": True,"offset_us": n} for t,n in [
        ("birthday",0),("post_service",0),("rebooking",86400000000),("inactivity",172800000000),
        ("package_expiry",86400000000),("subscription_renewal",86400000000)]))
    customer = RegisteredCustomerFact(institute_id="i",customer_id="c",created_at=clock(1))
    sources = tuple(EventAnchor(institute_id="i",customer_id="c",source_id=k,source_kind=k,
        occurred_at=clock(5),expires_at=clock(8) if k != "care_episode" else None,
        remaining=2 if k == "package" else None) for k in ["birthday","care_episode","package","membership"])
    return policy,customer,sources

def test_all_six_exact_boundaries_repeatability_and_retained_source_terms():
    p,c,s=fixture();r=candidates(p,"original",c,clock(7),s)
    assert len(r)==6
    assert {v.rule.trigger for v in r}=={"birthday","post_service","rebooking","inactivity","package_expiry","subscription_renewal"}
    assert all(v.state=="due" and not v.delivery_authorized and not v.external_message_sent for v in r)
    assert candidates(p,"original",c,clock(7),s)==r
    assert r[2].due_at==clock(6) and r[3].due_at==clock(7)
    assert r[4].due_at==clock(7) and r[4].source.remaining==2
    expired=candidates(p,"original",c,clock(8),s)
    assert [v.state for v in expired]==["expired","due","due","due","expired","expired"]

def test_latest_care_only_for_recency_triggers_no_invented_source_and_disabled_exhaustion():
    p,c,s=fixture();new=EventAnchor(institute_id="i",customer_id="c",source_id="latest",source_kind="care_episode",occurred_at=clock(6),expires_at=None,remaining=None)
    r=candidates(p,"original",c,clock(7),s+(new,))
    assert len(r)==7
    assert next(v for v in r if v.rule.trigger=="inactivity").state=="scheduled"
    assert all(v.source.source_id=="latest" for v in r if v.rule.trigger in {"inactivity","rebooking"})
    assert candidates(p,"original",c,clock(7),())==()
    exhausted=s[2].model_copy(update={"remaining":0})
    assert next(v for v in candidates(p,"original",c,clock(7),(exhausted,)) if v.rule.trigger=="package_expiry").state=="exhausted"
    terms=p.model_dump();terms["rules"][4]["enabled"]=False
    assert candidates(AutomationPolicy.model_validate(terms),"original",c,clock(7),(exhausted,))[0].state=="disabled"

@pytest.mark.parametrize("change", [{"customer_id":"foreign"},{"institute_id":"foreign"},{"occurred_at":clock(9)},{"occurred_at":datetime(2025,1,1,tzinfo=timezone.utc)}])
def test_foreign_future_or_pre_registration_observed_source_is_refused(change):
    p,c,s=fixture();bad=EventAnchor.model_validate({**s[1].model_dump(),**change})
    with pytest.raises(ValueError): candidates(p,"original",c,clock(7),(bad,))

def test_duplicate_naive_clock_invalid_balance_and_overflow_are_refused():
    p,c,s=fixture()
    with pytest.raises(ValueError): candidates(p,"original",c,clock(7),s+(s[1],))
    with pytest.raises(ValidationError): EventAnchor.model_validate({**s[2].model_dump(),"remaining":True})
    with pytest.raises(ValidationError): EventAnchor.model_validate({**s[1].model_dump(),"occurred_at":datetime(2026,10,5)})
    terms=p.model_dump();terms["rules"][1]["offset_us"]=253402300799999999
    with pytest.raises(ValueError): candidates(AutomationPolicy.model_validate(terms),"original",c,clock(7),(s[1],))
