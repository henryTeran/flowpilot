import pytest
from pydantic import ValidationError
from app.modules.crm.automation_policy import AutomationPolicy


def terms():
    return {"institute_id": "i", "rules": [
        {"trigger": trigger, "enabled": False, "offset_us": offset}
        for trigger, offset in [("birthday", 0), ("post_service", 0),
                                ("rebooking", 86400000000), ("inactivity", 172800000000),
                                ("package_expiry", 0), ("subscription_renewal", 0)]]}


def test_complete_explicit_rules_preserve_large_microseconds_and_disabled_terms():
    value = terms()
    value["rules"][4]["offset_us"] = 9007199254740993
    policy = AutomationPolicy.model_validate(value)
    assert policy.model_dump() == {**value, "rules": tuple(value["rules"])}
    assert policy.rules[4].offset_us == 9007199254740993
    with pytest.raises(ValidationError):
        policy.rules[0].enabled = True


@pytest.mark.parametrize("mutation", [
    lambda v: v.pop("rules"),
    lambda v: v["rules"].pop(),
    lambda v: v["rules"].__setitem__(5, v["rules"][0]),
    lambda v: v["rules"][0].pop("enabled"),
    lambda v: v["rules"][0].__setitem__("enabled", "false"),
    lambda v: v["rules"][1].__setitem__("offset_us", True),
    lambda v: v["rules"][1].__setitem__("offset_us", 0.5),
    lambda v: v["rules"][1].__setitem__("offset_us", -1),
    lambda v: v["rules"][0].__setitem__("offset_us", 1),
    lambda v: v["rules"][2].__setitem__("offset_us", 0),
    lambda v: v["rules"][3].__setitem__("offset_us", 0),
    lambda v: v["rules"][5].__setitem__("offset_us", 253402300800000000),
    lambda v: v.__setitem__("institute_id", " i"),
    lambda v: v.__setitem__("delivery_authorized", True),
])
def test_missing_duplicate_coerced_or_incoherent_rules_fail_closed(mutation):
    value = terms()
    mutation(value)
    with pytest.raises(ValidationError):
        AutomationPolicy.model_validate(value)


def test_json_duration_is_exact_canonical_string_with_legacy_integer_read_support():
    value=terms();value["rules"][4]["offset_us"]="9007199254740993"
    policy=AutomationPolicy.model_validate(value)
    assert policy.rules[4].offset_us==9007199254740993
    assert policy.model_dump(mode="json")["rules"][4]["offset_us"]=="9007199254740993"
    assert AutomationPolicy.model_validate(policy.model_dump(mode="json"))==policy
    for bad in ("01","+1","1.0","1e3"," 1","-1","253402300800000000","9"*19):
        value["rules"][4]["offset_us"]=bad
        with pytest.raises(ValidationError):AutomationPolicy.model_validate(value)


def test_duration_schema_describes_canonical_output_and_legacy_input():
    from app.modules.crm.automation_policy import AutomationRule
    validation=AutomationRule.model_json_schema(mode="validation")["properties"]["offset_us"]
    serialization=AutomationRule.model_json_schema(mode="serialization")["properties"]["offset_us"]
    assert {v["type"] for v in validation["anyOf"]}=={"integer","string"}
    assert "type" not in validation
    assert serialization["type"]=="string" and serialization["maxLength"]==18
