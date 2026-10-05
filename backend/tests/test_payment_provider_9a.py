from decimal import Decimal, localcontext
from dataclasses import FrozenInstanceError
import pytest
from app.modules.payments.provider import PaymentAmount, PaymentRequest, ProviderResult, ProviderStatus, RawWebhook, VerifiedWebhook


def test_payment_boundary_preserves_units_and_scoped_immutable_intent():
    value = PaymentAmount(Decimal("10.3500"), "CHF")
    assert value.amount.as_tuple().exponent == -2
    request = PaymentRequest("institut", "ticket", value, "replay", "signed-actor")
    with pytest.raises(FrozenInstanceError):
        request.idempotency_key = "new"
    for amount in (10.35, "10.35", Decimal("NaN"), Decimal("Infinity"), Decimal("0"), Decimal("-1"), Decimal("1.001"), Decimal("100000000")):
        with pytest.raises(ValueError):
            PaymentAmount(amount, "CHF")
    with pytest.raises(ValueError):
        PaymentAmount(Decimal("1"), "USD")
    for values in (("", "ticket", value, "key", "actor"), ("inst", "ticket", value, " key ", "actor"), ("inst", "ticket", value, "key", "")):
        with pytest.raises(ValueError):
            PaymentRequest(*values)
    result = ProviderResult("external-reference", ProviderStatus.CAPTURED, value)
    assert VerifiedWebhook("event", result).result == result
    with pytest.raises(ValueError):
        ProviderResult("external-reference", "captured", value)
    raw = RawWebhook(b"sensitive provider body", {"Authorization": "secret"})
    assert "secret" not in repr(raw) and "sensitive" not in repr(raw)



def test_provider_values_do_not_inherit_decimal_context_or_mutable_headers():
    with localcontext() as context:
        context.prec = 2
        assert PaymentAmount(Decimal("10.35"), "CHF").amount == Decimal("10.35")
    headers = {"signature": "original"}
    raw = RawWebhook(b"body", headers)
    headers["signature"] = "changed"
    assert raw.headers["signature"] == "original"
    with pytest.raises(TypeError):
        raw.headers["signature"] = "changed"
    with pytest.raises(ValueError):
        RawWebhook("body", headers)



@pytest.mark.parametrize("kind,status", [("authorize", "authorized"), ("capture", "captured"), ("refund", "refunded"), ("cancel", "cancelled")])
def test_results_match_original_amount_reference_and_operation(kind, status):
    from app.modules.payments.provider import OperationKind, validate_result
    value = PaymentAmount(Decimal("10.35"), "CHF")
    request = PaymentRequest("inst", "ticket", value, "operation", "actor")
    operation = OperationKind(kind)
    reference = None if kind == "authorize" else "original"
    for outcome in (ProviderStatus(status), ProviderStatus.PENDING, ProviderStatus.FAILED):
        result = ProviderResult("original", outcome, value)
        assert validate_result(request, operation, result, reference) is result
    for other in ProviderStatus:
        if other not in {ProviderStatus(status), ProviderStatus.PENDING, ProviderStatus.FAILED}:
            with pytest.raises(ValueError):
                validate_result(request, operation, ProviderResult("original", other, value), reference)
    for wrong in (PaymentAmount(Decimal("10.35"), "EUR"), PaymentAmount(Decimal("10.34"), "CHF")):
        with pytest.raises(ValueError):
            validate_result(request, operation, ProviderResult("original", ProviderStatus(status), wrong), reference)
    with pytest.raises(ValueError):
        validate_result(request, operation, ProviderResult("other", ProviderStatus(status), value), "original")
    if kind != "authorize":
        with pytest.raises(ValueError):
            validate_result(request, operation, ProviderResult("original", ProviderStatus(status), value))
