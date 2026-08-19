"""Synthetic tests for Week 6 policy and process decisions."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from referral_attribution.cleaning import has_configured_test_demo_signal
from referral_attribution.config import load_rules
from referral_attribution.process_rules import (
    apply_ownership_policy,
    evaluate_open_referral_warning,
)
from referral_attribution.quality import evaluate_value_sanity


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(PROJECT_ROOT)


def _policy(policy_id: str) -> dict:
    return next(
        policy
        for policy in RULES["process"]["multi_referrer"]["policies"]
        if policy["policy_id"] == policy_id
    )


def _pairs(records: list[dict]) -> pd.DataFrame:
    defaults = {
        "booking_id": "B1",
        "booking_project_id": "P1",
        "referral_project_id": "P1",
        "referral_enquiry_id": "R1",
        "referral_submitted_at": pd.Timestamp("2025-01-01"),
        "referrer_user_id": "U1",
        "referrer_name": "Referrer One",
        "days_between_referral_and_booking": 10.0,
    }
    return pd.DataFrame([{**defaults, **record} for record in records])


def test_strong_test_demo_signals_are_config_driven() -> None:
    bookings = pd.DataFrame(
        {
            "booking_crm_id": ["DEMO-001", "LIVE-100", "LIVE-200"],
            "booking_unit_number": ["A101", "TEST", "B201"],
        }
    )

    flags = has_configured_test_demo_signal(
        bookings,
        RULES["filters"]["strong_test_demo_signals"]["bookings"],
    )

    assert flags.tolist() == [True, True, False]


def test_repeated_digit_value_is_flagged_without_dropping_context() -> None:
    flags = evaluate_value_sanity(
        pd.Series([11111111, 50000, None, 0]),
        rules=RULES,
    )

    assert flags.tolist() == [
        "Repeated-digit pattern",
        "Positive contextual value",
        "Not available",
        "Non-positive value",
    ]


def test_single_same_project_referrer_gets_soft_warning() -> None:
    outcome = evaluate_open_referral_warning(
        "DIRECT",
        prior_referral_count=1,
        prior_referrer_count=1,
        same_project_any=True,
        rules=RULES,
    )

    assert outcome["warning_shown"] is True
    assert outcome["warning_severity"] == "Medium"
    assert outcome["manual_review_required"] is False
    assert outcome["override_reason_required"] is False


def test_multiple_same_project_referrers_require_manual_override() -> None:
    outcome = evaluate_open_referral_warning(
        "DIRECT",
        prior_referral_count=3,
        prior_referrer_count=2,
        same_project_any=True,
        rules=RULES,
    )

    assert outcome["warning_shown"] is True
    assert outcome["warning_severity"] == "High"
    assert outcome["manual_review_required"] is True
    assert outcome["override_reason_required"] is True
    assert outcome["decision"] == "Escalate"


def test_cross_project_only_history_stays_low_severity() -> None:
    outcome = evaluate_open_referral_warning(
        "DIRECT",
        prior_referral_count=1,
        prior_referrer_count=1,
        same_project_any=False,
        rules=RULES,
    )

    assert outcome["warning_shown"] is True
    assert outcome["warning_severity"] == "Low"
    assert outcome["manual_review_required"] is False


def test_manual_policy_blocks_auto_owner_for_multiple_referrers() -> None:
    pairs = _pairs(
        [
            {
                "referral_enquiry_id": "R-OLD",
                "referral_submitted_at": pd.Timestamp("2025-01-01"),
                "referrer_user_id": "U1",
            },
            {
                "referral_enquiry_id": "R-LATEST",
                "referral_submitted_at": pd.Timestamp("2025-01-15"),
                "referrer_user_id": "U2",
            },
        ]
    )

    outcome = apply_ownership_policy(
        pairs,
        _policy("P-MANUAL"),
        manual_referrer_threshold=2,
    ).iloc[0]

    assert bool(outcome["manual_review_required"]) is True
    assert bool(outcome["auto_assignable"]) is False
    assert pd.isna(outcome["auto_owner_referrer_user_id"])
    assert outcome["reference_referrer_user_id"] == "U2"


def test_latest_policy_uses_latest_referrer_as_a_reference() -> None:
    pairs = _pairs(
        [
            {
                "referral_enquiry_id": "R-OLD",
                "referral_submitted_at": pd.Timestamp("2025-01-01"),
                "referrer_user_id": "U1",
            },
            {
                "referral_enquiry_id": "R-LATEST",
                "referral_submitted_at": pd.Timestamp("2025-01-15"),
                "referrer_user_id": "U2",
            },
        ]
    )

    outcome = apply_ownership_policy(
        pairs,
        _policy("P-LAST"),
        manual_referrer_threshold=2,
    ).iloc[0]

    assert bool(outcome["auto_assignable"]) is True
    assert outcome["auto_owner_referrer_user_id"] == "U2"
