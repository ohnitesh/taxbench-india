import pytest

from taxbench.reference import (
    eway_required,
    eway_validity_days,
    gst_split,
    gst_split_inclusive,
    gstin_check_digit,
    gstin_validate,
    tds_amount,
)

# The sample GSTIN used across GST documentation and tooling.
SAMPLE = "27AAPFU0939F1ZV"


def test_check_digit_matches_published_sample():
    assert gstin_check_digit(SAMPLE[:14]) == SAMPLE[14]
    assert gstin_validate(SAMPLE) == {"valid": True}


def test_check_digit_rejects_bad_input():
    with pytest.raises(ValueError):
        gstin_check_digit("27AAPFU0939F1")
    with pytest.raises(ValueError):
        gstin_check_digit("27AAPFU0939F1-")


@pytest.mark.parametrize(
    "gstin",
    [
        "27AAPFU0939F1ZA",  # wrong check digit
        "27AAPFU0939F1Z",  # too short
        "27AAPFU0939F1ZVV",  # too long
        "2XAAPFU0939F1ZV",  # state code not numeric
        "27AAPFU0939F0ZV",  # entity code cannot be 0
        "",
    ],
)
def test_validate_rejects(gstin):
    assert gstin_validate(gstin) == {"valid": False}


def test_validate_ignores_case_and_spaces():
    assert gstin_validate(f"  {SAMPLE.lower()} ") == {"valid": True}


def test_split_same_state_is_halved():
    assert gst_split(20000, 5, "08", "08") == {"cgst": 500.0, "sgst_utgst": 500.0, "igst": 0.0, "invoice_total": 21000.0}


def test_split_other_state_is_igst():
    assert gst_split(150000, 18, "08", "24") == {"cgst": 0.0, "sgst_utgst": 0.0, "igst": 27000.0, "invoice_total": 177000.0}


def test_split_components_add_up():
    result = gst_split(1250, 5, "08", "08")
    assert result["cgst"] + result["sgst_utgst"] + result["igst"] == pytest.approx(62.5)


def test_inclusive_split_recovers_taxable_value():
    result = gst_split_inclusive(11800, 18, "08", "08")
    assert result["taxable_value"] == 10000.0
    assert result["cgst"] == result["sgst_utgst"] == 900.0
    assert result["invoice_total"] == 11800.0


@pytest.mark.parametrize("km,per_day,days", [(1, 200, 1), (200, 200, 1), (201, 200, 2), (310, 200, 2), (400, 200, 2), (45, 20, 3), (20, 20, 1)])
def test_eway_validity(km, per_day, days):
    assert eway_validity_days(km, per_day) == {"validity_days": days}


def test_eway_validity_needs_positive_distance():
    with pytest.raises(ValueError):
        eway_validity_days(0, 200)


def test_eway_threshold_uses_value_with_tax():
    assert eway_required(48000, 18, 50000) == {"consignment_value": 56640.0, "eway_bill_required": True}
    assert eway_required(42000, 18, 50000)["eway_bill_required"] is False


def test_eway_exactly_at_threshold_is_not_required():
    assert eway_required(50000, 0, 50000)["eway_bill_required"] is False


def test_tds_single_payment_over_limit():
    assert tds_amount(40000, 2, single_threshold=30000, aggregate_threshold=100000) == {"tds_amount": 800.0}


def test_tds_under_both_limits():
    assert tds_amount(25000, 1, 30000, 100000, prior_aggregate=60000) == {"tds_amount": 0.0}


def test_tds_first_crossing_of_aggregate_covers_earlier_payments():
    assert tds_amount(20000, 1, 30000, 100000, prior_aggregate=90000) == {"tds_amount": 1100.0}


def test_tds_after_aggregate_already_crossed_covers_this_payment_only():
    assert tds_amount(20000, 1, 30000, 100000, prior_aggregate=150000, prior_tds_deducted=True) == {"tds_amount": 200.0}


def test_tds_exactly_at_limit_is_not_deductible():
    assert tds_amount(50000, 10, aggregate_threshold=50000) == {"tds_amount": 0.0}


def test_tds_without_limits_applies_to_the_payment():
    assert tds_amount(1000, 10) == {"tds_amount": 100.0}
