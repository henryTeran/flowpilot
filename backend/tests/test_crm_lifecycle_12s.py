from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
import pytest
from pydantic import ValidationError
from app.modules.crm.lifecycle import BirthdayCalendarPolicy,BirthdayCapture,LifecycleDeclaration,observe_birthday
from app.modules.crm.segments import RegisteredCustomerFact

def declaration(**changes):
    return LifecycleDeclaration(**dict(dict(institute_id="i",customer_id="customer_a",birthday={"month":10,"day":7},
        birthday_evidence="Customer declared month/day",communications=[dict(channel=channel,purpose=purpose,permission="unknown",evidence=None)
            for channel in ("email","sms") for purpose in ("service_follow_up","marketing")]),**changes))

def observe(instant="2026-10-07T00:00:00Z",zone="Europe/Zurich",leap="leap_year_only",decl=None):
    policy=BirthdayCalendarPolicy(institute_id="i",timezone=zone,leap_day=leap)
    capture=BirthdayCapture(institute_id="i",customer_id="customer_a",captured_at=instant)
    customer=RegisteredCustomerFact(institute_id="i",customer_id="customer_a",created_at="2020-01-01T00:00:00Z")
    return observe_birthday(decl or declaration(),policy,customer,capture)

def test_local_calendar_changes_day_without_inferring_communication_permission():
    due=observe("2026-10-06T22:00:00Z")
    assert due.due and str(due.local_date)=="2026-10-07" and due.reason=="birthday_today"
    assert due.occurrence_start==datetime(2026,10,6,22,tzinfo=timezone.utc)
    assert not due.delivery_authorized and not due.external_message_sent
    assert observe("2026-10-06T21:59:59.999999Z").reason=="not_today"
    assert observe("2026-10-07T00:00:00Z",zone="America/Los_Angeles").reason=="not_today"

@pytest.mark.parametrize("instant,month,day,hours",[("2026-03-29T12:00:00Z",3,29,23),("2026-10-25T12:00:00Z",10,25,25)])
def test_dst_occurrence_uses_civil_day_not_fixed_duration(instant,month,day,hours):
    r=observe(instant,decl=declaration(birthday={"month":month,"day":day}))
    assert r.due and r.occurrence_end-r.occurrence_start==timedelta(hours=hours)

@pytest.mark.parametrize("leap,instant,reason",[("leap_year_only","2026-02-28T12:00:00Z","absent_in_calendar_year"),
    ("february_28","2026-02-28T12:00:00Z","birthday_today"),("march_1","2026-03-01T12:00:00Z","birthday_today"),
    ("march_1","2028-02-29T12:00:00Z","birthday_today")])
def test_explicit_leap_day_policy(leap,instant,reason):
    r=observe(instant,leap=leap,decl=declaration(birthday={"month":2,"day":29}))
    assert r.reason==reason

def test_unknown_birthday_and_recorded_refusal_are_not_guessed_or_delivery_authority():
    decl=declaration(birthday=None,birthday_evidence=None)
    r=observe(decl=decl); assert r.reason=="birthday_unknown" and r.occurrence_start is r.occurrence_end is None
    raw=declaration().model_dump();raw["communications"][0]["permission"]="granted";raw["communications"][0]["evidence"]="Explicit recorded permission"
    recorded=LifecycleDeclaration(**raw);assert not observe(decl=recorded).delivery_authorized
    assert all(c.permission=="unknown" for c in recorded.communications[1:])
    raw["communications"][0]["permission"]="refused";raw["communications"][0]["evidence"]="Explicit recorded refusal"
    refused=LifecycleDeclaration(**raw);assert refused.communications[0].permission=="refused"
    assert not observe(decl=refused).delivery_authorized

@pytest.mark.parametrize("changes",[{"birthday":{"month":2,"day":30}},{"birthday":{"month":True,"day":1}},
    {"birthday":None},{"birthday_evidence":None},{"communications":[]}])
def test_invalid_or_partial_declarations_refused(changes):
    with pytest.raises(ValidationError): declaration(**changes)

def test_channels_purposes_evidence_scope_and_explicit_clock_required():
    raw=declaration().model_dump()
    for permission,evidence in (("granted",None),("refused",None),("unknown","Unproven reference")):
        item={**raw["communications"][0],"permission":permission,"evidence":evidence}
        with pytest.raises(ValidationError): declaration(communications=[item,*raw["communications"][1:]])
    with pytest.raises(ValidationError): declaration(communications=[raw["communications"][0]]*4)
    with pytest.raises(ValidationError): BirthdayCalendarPolicy(institute_id="i",timezone="Unknown/Zone",leap_day="leap_year_only")
    with pytest.raises(ValidationError): BirthdayCapture(institute_id="i",customer_id="customer_a",captured_at="2026-10-07")
    with pytest.raises(ValueError): observe(decl=declaration(customer_id="foreign"))

def test_registration_and_policy_scope_and_unrepresentable_calendar_refused():
    decl=declaration();policy=BirthdayCalendarPolicy(institute_id="i",timezone="UTC",leap_day="leap_year_only")
    capture=BirthdayCapture(institute_id="i",customer_id="customer_a",captured_at="2026-10-07T00:00:00Z")
    for changes in ({"institute_id":"foreign"},{"customer_id":"other"},{"created_at":"2026-10-07T00:00:00.000001Z"}):
        customer=RegisteredCustomerFact(**dict(dict(institute_id="i",customer_id="customer_a",created_at="2020-01-01T00:00:00Z"),**changes))
        with pytest.raises(ValueError): observe_birthday(decl,policy,customer,capture)
    foreign=BirthdayCalendarPolicy(institute_id="foreign",timezone="UTC",leap_day="leap_year_only")
    customer=RegisteredCustomerFact(institute_id="i",customer_id="customer_a",created_at="0001-01-01T00:00:00Z")
    with pytest.raises(ValueError): observe_birthday(decl,foreign,customer,capture)
    capture=BirthdayCapture(institute_id="i",customer_id="customer_a",captured_at="9999-12-31T12:00:00Z")
    with pytest.raises(ValueError): observe_birthday(declaration(birthday={"month":12,"day":31}),policy,customer,capture)

def test_repeated_wall_clock_hour_compares_registration_in_actual_utc_order():
    zone=ZoneInfo("Europe/Zurich")
    customer=RegisteredCustomerFact(institute_id="i",customer_id="customer_a",created_at=datetime(2026,10,25,2,45,tzinfo=zone,fold=0))
    capture=BirthdayCapture(institute_id="i",customer_id="customer_a",captured_at=datetime(2026,10,25,2,15,tzinfo=zone,fold=1))
    policy=BirthdayCalendarPolicy(institute_id="i",timezone="Europe/Zurich",leap_day="leap_year_only")
    assert observe_birthday(declaration(birthday={"month":10,"day":25}),policy,customer,capture).due
