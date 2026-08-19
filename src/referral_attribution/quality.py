"""Data-quality summaries and regression validation."""

from __future__ import annotations

import pandas as pd


EXPECTED_WEEK5_REGRESSION = {
    "eligible_bookings": 12,
    "strict_honored": 8,
    "primary_review": 4,
    "tier_a": 0,
    "tier_b": 4,
    "tier_c": 3,
    "reverse_time_source_disagreement": 28,
    "time_valid_same_enquiry_strict_unhonored": 0,
}

EXPECTED_STRONG_SIGNAL_SENSITIVITY = {
    "eligible_bookings": 11,
    "strict_honored": 7,
    "primary_review": 4,
    "tier_a": 0,
    "tier_b": 4,
    "tier_c": 3,
    "reverse_time_source_disagreement": 28,
    "time_valid_same_enquiry_strict_unhonored": 0,
}

# Kept for existing external imports; the default JSON uses the accepted baseline.
EXPECTED_REGRESSION = EXPECTED_WEEK5_REGRESSION
EXPECTED_PRIMARY_BOOKING_IDS = {"1206", "935", "3331", "4913"}


def validate_primary_queue_integrity(primary_matches: pd.DataFrame) -> None:
    """Fail loudly if the primary queue violates its grain or time contract."""
    required = {
        "booking_id",
        "booking_timeline_at",
        "referral_submitted_at",
    }
    missing = sorted(required - set(primary_matches.columns))
    if missing:
        raise ValueError(
            f"Primary queue is missing integrity columns: {missing}"
        )

    duplicate_booking_ids = primary_matches["booking_id"].duplicated().sum()
    if duplicate_booking_ids:
        raise AssertionError(
            "Primary queue must contain one row per booking; "
            f"found {int(duplicate_booking_ids)} duplicate booking rows."
        )

    missing_timeline = (
        primary_matches["booking_timeline_at"].isna()
        | primary_matches["referral_submitted_at"].isna()
    )
    if missing_timeline.any():
        raise AssertionError(
            "Primary queue contains rows without a usable referral or booking time."
        )

    reverse_time = primary_matches["referral_submitted_at"].gt(
        primary_matches["booking_timeline_at"]
    )
    if reverse_time.any():
        invalid_ids = sorted(
            primary_matches.loc[reverse_time, "booking_id"]
            .astype("string")
            .tolist()
        )
        raise AssertionError(
            "Primary queue contains reverse-time matches. "
            f"Booking IDs: {invalid_ids}"
        )


def build_data_quality_summary(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    rules: dict | None = None,
) -> pd.DataFrame:
    """Summarize key grain, date, and filter checks."""
    filters = (rules or {}).get("filters", {})
    test_demo_enabled = bool(filters.get("test_demo_enabled", True))
    strong_signal_enabled = bool(filters.get("strong_test_demo_enabled", False))
    name_status = "Filtered" if test_demo_enabled else "Not applied"
    strong_status = "Filtered" if strong_signal_enabled else "Flagged"
    return pd.DataFrame(
        [
            {
                "check": "Referral rows",
                "value": len(referrals),
                "status": "Info",
            },
            {
                "check": "Booking rows",
                "value": len(bookings),
                "status": "Info",
            },
            {
                "check": "Duplicate referral enquiry IDs",
                "value": int(referrals["referral_enquiry_id"].duplicated().sum()),
                "status": "Pass",
            },
            {
                "check": "Duplicate booking IDs",
                "value": int(bookings["booking_id"].duplicated().sum()),
                "status": "Pass",
            },
            {
                "check": "Referral rows with parsed submitted time",
                "value": int(referrals["referral_submitted_at"].notna().sum()),
                "status": "Info",
            },
            {
                "check": "Bookings with usable timeline",
                "value": int(bookings["booking_timeline_at"].notna().sum()),
                "status": "Info",
            },
            {
                "check": "Referral name-pattern test/demo rows",
                "value": int(
                    referrals["referral_test_demo_name_flag"].fillna(False).sum()
                ),
                "status": name_status,
            },
            {
                "check": "Referral strong-signal test/demo rows",
                "value": int(
                    referrals[
                        "referral_test_demo_strong_signal_flag"
                    ].fillna(False).sum()
                ),
                "status": strong_status,
            },
            {
                "check": "Booking name-pattern test/demo rows",
                "value": int(
                    bookings["booking_test_demo_name_flag"].fillna(False).sum()
                ),
                "status": name_status,
            },
            {
                "check": "Booking strong-signal test/demo rows",
                "value": int(
                    bookings[
                        "booking_test_demo_strong_signal_flag"
                    ].fillna(False).sum()
                ),
                "status": strong_status,
            },
            {
                "check": "Booking rows excluded by active test/demo filter",
                "value": int(bookings["booking_test_demo_flag"].sum()),
                "status": name_status,
            },
        ]
    )


def evaluate_value_sanity(
    series: pd.Series,
    rules: dict | None = None,
) -> pd.Series:
    """Flag unusable or keyboard-pattern values without dropping a case."""
    settings = (rules or {}).get("quality", {}).get("value_sanity", {})
    minimum_length = int(settings.get("repeated_digit_min_length", 6))
    missing_label = settings.get("missing_label", "Not available")
    non_positive_label = settings.get("non_positive_label", "Non-positive value")
    repeated_label = settings.get("repeated_digit_label", "Repeated-digit pattern")
    positive_label = settings.get("positive_label", "Positive contextual value")

    numeric = pd.to_numeric(series, errors="coerce")
    integer_like = numeric.notna() & numeric.mod(1).eq(0)
    integer_text = numeric.where(integer_like).round().astype("Int64").astype("string")
    repeated_digits = integer_text.str.fullmatch(
        rf"(\d)\1{{{minimum_length - 1},}}",
        na=False,
    )
    return pd.Series(
        pd.Series(
            pd.NA,
            index=series.index,
            dtype="string",
        )
        .mask(numeric.isna(), missing_label)
        .mask(numeric.notna() & numeric.le(0), non_positive_label)
        .mask(numeric.gt(0) & repeated_digits, repeated_label)
        .fillna(positive_label),
        index=series.index,
        dtype="string",
    )


def _regression_contract(rules: dict | None) -> tuple[dict[str, int], set[str]]:
    """Choose the explicit regression contract for the active test filter."""
    if rules is None:
        return EXPECTED_WEEK5_REGRESSION, EXPECTED_PRIMARY_BOOKING_IDS

    regression = rules.get("regression", {})
    filters = rules.get("filters", {})
    if not filters.get("test_demo_enabled", True):
        raise ValueError(
            "No accepted regression contract is defined when test/demo filtering is disabled."
        )
    contract_name = (
        "strong_signal_sensitivity"
        if filters.get("strong_test_demo_enabled", False)
        else "accepted_week5_baseline"
    )
    contract = regression.get(contract_name)
    if not contract:
        raise ValueError(f"Missing regression contract: {contract_name}")
    return contract["metrics"], set(contract["primary_review_booking_ids"])


def validate_regression(
    primary_matches: pd.DataFrame,
    primary_review: pd.DataFrame,
    tier_c_review: pd.DataFrame,
    reverse_time: pd.DataFrame,
    same_enquiry_time_valid: pd.DataFrame,
    rules: dict | None = None,
) -> dict[str, int]:
    """Assert the active JSON rule contract and primary review IDs."""
    actual = {
        "eligible_bookings": primary_matches["booking_id"].nunique(),
        "strict_honored": primary_matches.loc[
            primary_matches["honored_strict"], "booking_id"
        ].nunique(),
        "primary_review": primary_review["booking_id"].nunique(),
        "tier_a": int(
            primary_review["confidence_tier"].str.startswith("Tier A").sum()
        ),
        "tier_b": int(
            primary_review["confidence_tier"].str.startswith("Tier B").sum()
        ),
        "tier_c": tier_c_review["booking_id"].nunique(),
        "reverse_time_source_disagreement": len(reverse_time),
        "time_valid_same_enquiry_strict_unhonored": int(
            (~same_enquiry_time_valid["same_enquiry_honored_strict"]).sum()
        ),
    }
    expected_metrics, expected_booking_ids = _regression_contract(rules)
    differences = {
        metric: {"expected": expected, "actual": actual[metric]}
        for metric, expected in expected_metrics.items()
        if actual[metric] != expected
    }
    if differences:
        raise AssertionError(
            "Configured regression values changed. Investigate rules, filters, "
            f"dates, identity keys, or implementation: {differences}"
        )

    booking_ids = set(primary_review["booking_id"].dropna().astype("string"))
    if booking_ids != expected_booking_ids:
        raise AssertionError(
            "Primary review booking IDs changed. "
            f"Expected {sorted(expected_booking_ids)}, "
            f"found {sorted(booking_ids)}."
        )
    return actual
