"""Data-quality summaries and regression validation."""

from __future__ import annotations

import pandas as pd


EXPECTED_REGRESSION = {
    "eligible_bookings": 12,
    "strict_honored": 8,
    "primary_review": 4,
    "tier_a": 0,
    "tier_b": 4,
    "tier_c": 3,
    "reverse_time_source_disagreement": 28,
    "time_valid_same_enquiry_strict_unhonored": 0,
}

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
) -> pd.DataFrame:
    """Summarize key grain, date, and filter checks."""
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
                "check": "Referral test/demo rows",
                "value": int(referrals["referral_test_demo_flag"].sum()),
                "status": "Filtered",
            },
            {
                "check": "Booking test/demo rows",
                "value": int(bookings["booking_test_demo_flag"].sum()),
                "status": "Filtered",
            },
        ]
    )


def validate_regression(
    primary_matches: pd.DataFrame,
    primary_review: pd.DataFrame,
    tier_c_review: pd.DataFrame,
    reverse_time: pd.DataFrame,
    same_enquiry_time_valid: pd.DataFrame,
) -> dict[str, int]:
    """Assert that modularization did not change the accepted baseline."""
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
    differences = {
        metric: {"expected": expected, "actual": actual[metric]}
        for metric, expected in EXPECTED_REGRESSION.items()
        if actual[metric] != expected
    }
    if differences:
        raise AssertionError(
            "Accepted regression values changed. Investigate rules, filters, "
            f"dates, identity keys, or implementation: {differences}"
        )

    booking_ids = set(primary_review["booking_id"].dropna().astype("string"))
    if booking_ids != EXPECTED_PRIMARY_BOOKING_IDS:
        raise AssertionError(
            "Primary review booking IDs changed. "
            f"Expected {sorted(EXPECTED_PRIMARY_BOOKING_IDS)}, "
            f"found {sorted(booking_ids)}."
        )
    return actual
