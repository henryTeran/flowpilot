"""Exact recorded Numeric(10,2) source classification."""
from decimal import Decimal, InvalidOperation


def amount_fact(value):
    """Preserve absent/invalid Numeric(10,2) without float or context rounding."""
    if value is None:
        return None, "missing"
    if not isinstance(value, (Decimal, str)):
        return None, "invalid"
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None, "invalid"
    if not amount.is_finite() or amount < 0 or amount > Decimal("99999999.99"):
        return None, "invalid"
    if amount.is_zero():
        return "0", "known"
    _, digits, exponent = amount.as_tuple()
    if exponent < -2:
        extra = -2-exponent
        if extra >= len(digits) or any(digits[-extra:]):
            return None, "invalid"
        digits = digits[:-extra]
        exponent = -2
    coefficient = int("".join(map(str, digits)))
    return str(coefficient * 10**(exponent+2)), "known"

