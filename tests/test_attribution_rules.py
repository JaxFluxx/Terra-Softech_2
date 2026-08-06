"""Focused rule tests using fictional records only."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from referral_attribution.classification import (
    classify_primary_matches,
    classify_secondary_matches,
)
from referral_attribution.cleaning import (
    has_test_demo_name,
    normalize_bookings,
)
from referral_attribution.config import load_rules
from referral_attribution.io import validate_required_columns
from referral_attribution.matching import (
    build_time_valid_pairs,
    select_latest_prior_referral,
)
from referral_attribution.quality import validate_primary_queue_integrity
from referral_attribution.run_tracking import RunTracker, normalize_run_id


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES = load_rules(PROJECT_ROOT)


def _referral_rows(records: list[dict]) -> pd.DataFrame:
    defaults = {
        "client_name": "Client A",
        "referral_enquiry_id": "R1",
        "referral_submitted_at": pd.Timestamp("2025-01-01"),
        "referral_enquiry_status": "ENQUIRY",
        "stage": "OPEN",
        "referralSource": "CUSTOMER",
        "referralCode": "CODE",
        "sourcePlatform": "CRM",
        "referral_project_id": "P1",
        "projectName": "Project One",
        "referrer_user_id": "U1",
        "referrer_name": "Referrer",
        "referrer_user_type": "CUSTOMER",
        "referral_lead_id": "L1",
        "lead_name": "Lead",
        "lead_hash_id": "HASH",
        "referral_mobile_key": "MOBILE",
        "referral_email_key": "EMAIL",
        "referral_test_demo_flag": False,
    }
    return pd.DataFrame([{**defaults, **record} for record in records])


def _booking_rows(records: list[dict]) -> pd.DataFrame:
    defaults = {
        "client_name": "Client A",
        "booking_id": "B1",
        "booking_crm_id": "CRM-B1",
        "booking_timeline_at": pd.Timestamp("2025-02-01"),
        "booking_date_at": pd.Timestamp("2025-02-01"),
        "booking_created_at": pd.Timestamp("2025-01-31"),
        "bookingStatus": "BOOKING_DONE",
        "booking_source_norm": "DIRECT",
        "enquiry_id": "E1",
        "enquiry_source_norm": "DIRECT",
        "booking_lead_id": "L1",
        "lead_name": "Lead",
        "lead_hash_id": "HASH",
        "booking_project_id": "P1",
        "projectName": "Project One",
        "agreement_value": 100000.0,
        "honored_strict": False,
        "booking_test_demo_flag": False,
    }
    return pd.DataFrame([{**defaults, **record} for record in records])


def _raw_booking(source: str, enquiry_source: str = "DIRECT") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Client name": "Client A",
                "booking_id": "B1",
                "enquiry_id": "E1",
                "bookingDate": "2025-02-01",
                "booking_created_on": "2025-01-31",
                "booking_source": source,
                "enquiry_source": enquiry_source,
                "project_id": "P1",
                "lead_id": "L1",
                "lead_name": "Normal Lead",
                "mobileNumber": "MOBILE",
                "email": "EMAIL",
                "agreementValue": "100000",
            }
        ]
    )


def test_referral_after_booking_is_not_eligible() -> None:
    referrals = _referral_rows(
        [{"referral_submitted_at": pd.Timestamp("2025-03-01")}]
    )
    bookings = _booking_rows(
        [{"booking_timeline_at": pd.Timestamp("2025-02-01")}]
    )

    pairs = build_time_valid_pairs(referrals, bookings)

    assert pairs.empty


def test_strict_honored_only_accepts_booking_source_referral() -> None:
    direct_with_referral_enquiry = normalize_bookings(
        _raw_booking("DIRECT", "REFERRAL"),
        RULES,
    )
    referral_booking = normalize_bookings(
        _raw_booking("REFERRAL", "DIRECT"),
        RULES,
    )

    assert not bool(direct_with_referral_enquiry.loc[0, "honored_strict"])
    assert bool(referral_booking.loc[0, "honored_strict"])


def test_json_honored_values_change_runtime_behavior() -> None:
    custom_rules = deepcopy(RULES)
    custom_rules["honored"]["strict"]["accepted_values"] = [
        "CHANNEL_PARTNER"
    ]

    channel_partner_booking = normalize_bookings(
        _raw_booking("CHANNEL_PARTNER"),
        custom_rules,
    )
    referral_booking = normalize_bookings(
        _raw_booking("REFERRAL"),
        custom_rules,
    )

    assert bool(channel_partner_booking.loc[0, "honored_strict"])
    assert not bool(referral_booking.loc[0, "honored_strict"])


def test_json_same_day_rule_changes_time_gate_behavior() -> None:
    referrals = _referral_rows(
        [{"referral_submitted_at": pd.Timestamp("2025-02-01")}]
    )
    bookings = _booking_rows(
        [{"booking_timeline_at": pd.Timestamp("2025-02-01")}]
    )
    identity_rule = RULES["identity"]["primary_route"]

    inclusive = build_time_valid_pairs(
        referrals,
        bookings,
        identity_rule=identity_rule,
        allow_referral_on_booking_date=True,
    )
    exclusive = build_time_valid_pairs(
        referrals,
        bookings,
        identity_rule=identity_rule,
        allow_referral_on_booking_date=False,
    )

    assert len(inclusive) == 1
    assert exclusive.empty


def test_latest_prior_referral_is_selected() -> None:
    referrals = _referral_rows(
        [
            {
                "referral_enquiry_id": "R-OLD",
                "referral_submitted_at": pd.Timestamp("2025-01-01"),
            },
            {
                "referral_enquiry_id": "R-LATEST",
                "referral_submitted_at": pd.Timestamp("2025-01-20"),
            },
        ]
    )
    bookings = _booking_rows(
        [{"booking_timeline_at": pd.Timestamp("2025-02-01")}]
    )

    selected = select_latest_prior_referral(
        build_time_valid_pairs(referrals, bookings)
    )

    assert selected.loc[0, "referral_enquiry_id"] == "R-LATEST"
    assert selected.loc[0, "prior_referral_count"] == 2


def test_test_demo_name_is_detected() -> None:
    records = pd.DataFrame(
        {
            "lead_name": ["Normal Lead", "Demo Buyer", "test_user_12"],
            "referrer_name": ["Normal Referrer", "Normal Referrer", "Staff"],
        }
    )

    flags = has_test_demo_name(
        records,
        ["lead_name", "referrer_name"],
        RULES["filters"]["test_demo_pattern"],
    )

    assert flags.tolist() == [False, True, True]


def test_multiple_prior_referrers_produce_tier_b() -> None:
    matches = pd.DataFrame(
        [
            {
                "booking_id": "B1",
                "booking_timeline_at": pd.Timestamp("2025-02-01"),
                "honored_strict": False,
                "multiple_referrer_flag": True,
                "timeline_ambiguity_flag": False,
            }
        ]
    )

    _, review = classify_primary_matches(matches)

    assert review.loc[0, "confidence_tier"].startswith("Tier B")
    assert review.loc[0, "review_reason"] == "Multiple prior referrers"


def test_reverse_time_never_enters_primary_queue() -> None:
    referrals = _referral_rows(
        [{"referral_submitted_at": pd.Timestamp("2025-02-02")}]
    )
    bookings = _booking_rows(
        [{"booking_timeline_at": pd.Timestamp("2025-02-01")}]
    )

    pairs = build_time_valid_pairs(referrals, bookings)

    assert pairs.empty


def test_primary_queue_integrity_fails_loudly_on_reverse_time() -> None:
    invalid_queue = pd.DataFrame(
        [
            {
                "booking_id": "B1",
                "booking_timeline_at": pd.Timestamp("2025-02-01"),
                "referral_submitted_at": pd.Timestamp("2025-02-02"),
            }
        ]
    )

    with pytest.raises(AssertionError, match="reverse-time"):
        validate_primary_queue_integrity(invalid_queue)


def test_tier_c_route_does_not_change_primary_review_count() -> None:
    primary_matches = pd.DataFrame(
        [
            {
                "booking_id": "PRIMARY-1",
                "booking_timeline_at": pd.Timestamp("2025-02-01"),
                "honored_strict": False,
                "multiple_referrer_flag": True,
                "timeline_ambiguity_flag": False,
            }
        ]
    )
    secondary_matches = pd.DataFrame(
        [
            {
                "booking_id": "SECONDARY-1",
                "booking_timeline_at": pd.Timestamp("2025-02-01"),
                "honored_strict": False,
                "identity_collision_flag": False,
            }
        ]
    )

    _, primary_review = classify_primary_matches(primary_matches)
    tier_c_review = classify_secondary_matches(secondary_matches)

    assert len(primary_review) == 1
    assert len(tier_c_review) == 1
    assert primary_review.loc[0, "booking_id"] == "PRIMARY-1"


def test_missing_required_column_fails_loudly() -> None:
    table = pd.DataFrame({"booking_id": ["B1"]})

    with pytest.raises(ValueError, match="missing required columns"):
        validate_required_columns(
            table,
            {"booking_id", "booking_source"},
            "Fictional booking extract",
        )


def test_duplicate_booking_id_fails_loudly() -> None:
    duplicate_bookings = pd.concat(
        [_raw_booking("DIRECT"), _raw_booking("DIRECT")],
        ignore_index=True,
    )

    with pytest.raises(ValueError, match="booking_id is not unique"):
        normalize_bookings(duplicate_bookings, RULES)


def test_custom_config_path_is_supported(tmp_path: Path) -> None:
    custom_config = tmp_path / "custom_rules.json"
    custom_config.write_text(
        (PROJECT_ROOT / "config" / "attribution_rules.json").read_text(),
        encoding="utf-8",
    )

    loaded = load_rules(PROJECT_ROOT, config_path=custom_config)

    assert loaded["honored"]["primary_mode"] == "strict"
    assert loaded["time"]["latest_prior_referral"] is True


def test_run_tracker_writes_metadata_without_copying_source_rows(
    tmp_path: Path,
) -> None:
    raw_dir = tmp_path / "data" / "raw"
    raw_dir.mkdir(parents=True)
    source = raw_dir / "fictional.csv"
    source.write_text("id,value\nA1,10\n", encoding="utf-8")
    tracker = RunTracker(tmp_path, "fictional_run")

    inventory_path = tracker.write_inventory([source])
    tracker.write_plan()
    tracker.write_checkpoint(
        stage="pipeline",
        started_at="2026-01-01T00:00:00+00:00",
        regression={"eligible_bookings": 0},
        output_files=[],
    )

    inventory_text = inventory_path.read_text(encoding="utf-8")
    assert "data/raw/fictional.csv" in inventory_text
    assert "A1,10" not in inventory_text
    assert (tracker.checkpoints_dir / "pipeline.json").exists()
    assert normalize_run_id("safe_run-01") == "safe_run-01"

    with pytest.raises(ValueError, match="run_id"):
        normalize_run_id("../unsafe")
