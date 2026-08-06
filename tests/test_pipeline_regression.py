"""Accepted-dataset regression and repeatability checks."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from referral_attribution.pipeline import run_pipeline
from referral_attribution.quality import (
    EXPECTED_PRIMARY_BOOKING_IDS,
    EXPECTED_REGRESSION,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_OPS_COLUMNS = {
    "case_id",
    "confidence_tier",
    "case_class",
    "recommended_action",
    "priority",
    "booking_id",
    "booking_timeline_at",
    "booking_source_norm",
    "enquiry_source_norm",
    "lead_id",
    "lead_name",
    "referral_enquiry_id",
    "referral_submitted_at",
    "referrer_user_id",
    "referrer_name",
    "prior_referral_count",
    "prior_referrer_count",
    "days_between_referral_and_booking",
    "same_project",
    "timeline_ambiguity_flag",
    "value_sanity_flag",
    "agreement_value",
    "review_reason",
}


def test_accepted_regression_values_and_ids_remain_stable() -> None:
    result = run_pipeline(
        project_root=PROJECT_ROOT,
        write_outputs=False,
        verbose=False,
    )

    assert result["regression"] == EXPECTED_REGRESSION
    assert set(result["primary_review"]["booking_id"]) == (
        EXPECTED_PRIMARY_BOOKING_IDS
    )
    assert REQUIRED_OPS_COLUMNS.issubset(
        result["tables"]["ops_review_board.csv"].columns
    )


def test_repeated_pipeline_execution_is_stable() -> None:
    first = run_pipeline(
        project_root=PROJECT_ROOT,
        write_outputs=False,
        verbose=False,
    )
    second = run_pipeline(
        project_root=PROJECT_ROOT,
        write_outputs=False,
        verbose=False,
    )

    for filename in [
        "lifecycle_funnel_summary.csv",
        "attribution_window_sensitivity.csv",
        "ops_review_board.csv",
    ]:
        pd.testing.assert_frame_equal(
            first["tables"][filename],
            second["tables"][filename],
            check_dtype=True,
        )
