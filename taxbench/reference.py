"""Reference calculators.

These exist to check the expected values written in case files. A case that
declares a ``reference`` block is recomputed here by ``taxbench validate``, so a
typo in a case file fails CI instead of becoming a wrong benchmark answer.

Nothing in this module looks up rates or thresholds on its own. Every rate,
threshold and date is passed in by the case, and the case carries the source.
"""

from __future__ import annotations

import math
import re
from decimal import ROUND_HALF_UP, Decimal

GSTIN_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

# Union territories without a legislature levy UTGST instead of SGST. The amount
# is the same, so cases report one combined key: ``sgst_utgst``.
_GSTIN_SHAPE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def gstin_check_digit(first14: str) -> str:
    """Return the 15th character of a GSTIN from its first 14 characters."""
    if len(first14) != 14:
        raise ValueError("need exactly 14 characters")
    total = 0
    for index, char in enumerate(first14.upper()):
        if char not in GSTIN_ALPHABET:
            raise ValueError(f"character {char!r} is not allowed in a GSTIN")
        product = GSTIN_ALPHABET.index(char) * (2 if index % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_ALPHABET[(36 - total % 36) % 36]


def gstin_validate(gstin: str) -> dict:
    """Check length, shape and check digit. Does not prove the GSTIN is registered."""
    value = gstin.strip().upper()
    if len(value) != 15:
        return {"valid": False}
    if not _GSTIN_SHAPE.match(value):
        return {"valid": False}
    return {"valid": gstin_check_digit(value[:14]) == value[14]}


def gst_split(taxable_value: float, rate_percent: float, supplier_state: str, pos_state: str) -> dict:
    """Split GST on a tax-exclusive value.

    Same state for supplier and place of supply means CGST plus SGST/UTGST in
    equal halves. Different states means IGST.
    """
    value = Decimal(str(taxable_value))
    tax = value * Decimal(str(rate_percent)) / Decimal(100)
    if str(supplier_state) == str(pos_state):
        half = tax / 2
        cgst, sgst, igst = half, half, Decimal(0)
    else:
        cgst, sgst, igst = Decimal(0), Decimal(0), tax
    return {
        "cgst": _money(cgst),
        "sgst_utgst": _money(sgst),
        "igst": _money(igst),
        "invoice_total": _money(value + tax),
    }


def gst_split_inclusive(inclusive_value: float, rate_percent: float, supplier_state: str, pos_state: str) -> dict:
    """Split GST out of a tax-inclusive price (tax = price x rate / (100 + rate))."""
    price = Decimal(str(inclusive_value))
    rate = Decimal(str(rate_percent))
    taxable = price * Decimal(100) / (Decimal(100) + rate)
    result = gst_split(float(taxable), rate_percent, supplier_state, pos_state)
    result["taxable_value"] = _money(taxable)
    result["invoice_total"] = _money(price)
    return result


def eway_validity_days(distance_km: float, km_per_day: float) -> dict:
    """One day for each block of ``km_per_day`` or part of it."""
    if distance_km <= 0:
        raise ValueError("distance must be positive")
    return {"validity_days": math.ceil(distance_km / km_per_day)}


def eway_required(taxable_value: float, rate_percent: float, threshold: float) -> dict:
    """Consignment value includes the GST charged. Required when it exceeds the threshold."""
    value = Decimal(str(taxable_value))
    consignment = value + value * Decimal(str(rate_percent)) / Decimal(100)
    return {
        "consignment_value": _money(consignment),
        "eway_bill_required": consignment > Decimal(str(threshold)),
    }


def tds_amount(
    amount: float,
    rate_percent: float,
    single_threshold: float | None = None,
    aggregate_threshold: float | None = None,
    prior_aggregate: float = 0.0,
    prior_tds_deducted: bool = False,
) -> dict:
    """TDS on one payment, given the rate and thresholds the case supplies.

    ``single_threshold``: deduct when this one payment exceeds it.
    ``aggregate_threshold``: deduct when the year's total to this payee exceeds
    it. When the aggregate limit is crossed for the first time, tax is due on
    the whole year's total, including earlier payments that had no deduction.
    """
    pay = Decimal(str(amount))
    rate = Decimal(str(rate_percent)) / Decimal(100)
    prior = Decimal(str(prior_aggregate))
    over_single = single_threshold is not None and pay > Decimal(str(single_threshold))
    over_aggregate = aggregate_threshold is not None and prior + pay > Decimal(str(aggregate_threshold))
    if single_threshold is None and aggregate_threshold is None:
        base = pay
    elif over_aggregate and not prior_tds_deducted:
        base = prior + pay
    elif over_single or over_aggregate:
        base = pay
    else:
        base = Decimal(0)
    return {"tds_amount": _money(base * rate)}


FUNCTIONS = {
    "gstin_validate": gstin_validate,
    "gst_split": gst_split,
    "gst_split_inclusive": gst_split_inclusive,
    "eway_validity_days": eway_validity_days,
    "eway_required": eway_required,
    "tds_amount": tds_amount,
}
