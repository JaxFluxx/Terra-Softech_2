"""Case classification and the operational review board."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _classification_rules(rules: dict | None) -> dict:
    """Provide accepted labels when unit tests omit the full JSON config."""
    if rules is not None:
        return rules["classification"]
    return {
        "tier_a": {"label": "Tier A - Strong attribution review"},
        "tier_b": {"label": "Tier B - Ambiguous attribution review"},
        "tier_c": {"label": "Tier C - Secondary identity review"},
        "primary_case_class": "Primary attribution review",
        "secondary_case_class": "Secondary identity review",
        "reverse_time_case_class": "Reverse-time data integrity",
        "ops_priorities": {
            "reverse_time": {"label": "P0 - Repair chronology", "order": 0},
            "primary_review": {"label": "P1 - Verify attribution", "order": 1},
            "secondary_review": {"label": "P2 - Confirm identity", "order": 2},
        },
    }


def _honored_definition(rules: dict | None) -> str:
    """Describe the configured honored rule in exported review tables."""
    if rules is None:
        return 'booking_source == "REFERRAL"'
    values = rules["honored"]["strict"]["accepted_values"]
    return f"booking source in {values}"


def classify_primary_matches(
    matches: pd.DataFrame,
    rules: dict | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the accepted primary review and confidence-tier rules."""
    classification = _classification_rules(rules)
    identity_label = (
        rules["identity"]["primary_route"]["label"]
        if rules is not None
        else "Exact client + lead_id"
    )
    classified = matches.assign(
        identity_rule=identity_label,
        match_rule="Latest time-valid prior referral; no default attribution window",
        candidate_status=lambda frame: np.where(
            frame["honored_strict"],
            "Honored under strict rule",
            "Possible bypass - review required",
        ),
        confidence_tier=lambda frame: np.select(
            [
                frame["honored_strict"],
                ~frame["honored_strict"]
                & ~frame["multiple_referrer_flag"]
                & ~frame["timeline_ambiguity_flag"],
                ~frame["honored_strict"],
            ],
            [
                "Not a bypass candidate",
                classification["tier_a"]["label"],
                classification["tier_b"]["label"],
            ],
            default="Unclassified",
        ),
    )
    review_cases = (
        classified.loc[~classified["honored_strict"]]
        .sort_values("booking_timeline_at")
        .assign(
            review_reason=lambda frame: np.select(
                [
                    frame["multiple_referrer_flag"]
                    & frame["timeline_ambiguity_flag"],
                    frame["multiple_referrer_flag"],
                    frame["timeline_ambiguity_flag"],
                ],
                [
                    "Multiple prior referrers and timeline ambiguity",
                    "Multiple prior referrers",
                    "Timeline ambiguity",
                ],
                default="Manual attribution review required",
            )
        )
    )
    return classified, review_cases


def classify_secondary_matches(
    matches: pd.DataFrame,
    rules: dict | None = None,
) -> pd.DataFrame:
    """Label exact encrypted-identity matches as a separate confirmation route."""
    if matches.empty:
        return matches

    classification = _classification_rules(rules)
    return matches.assign(
        confidence_tier=classification["tier_c"]["label"],
        candidate_status=lambda frame: np.where(
            frame["honored_strict"],
            "Honored under strict rule",
            "Possible bypass - identity confirmation required",
        ),
        review_reason=lambda frame: np.where(
            frame["identity_collision_flag"],
            "Exact encrypted identity match with lead-ID collision",
            "Exact encrypted identity match but booking and referral lead IDs differ",
        ),
    ).sort_values(["candidate_status", "booking_timeline_at"])


def _value_sanity(series: pd.Series) -> pd.Series:
    """Provide context on agreement value without treating it as impact."""
    return pd.Series(
        np.select(
            [series.isna(), series.le(0)],
            ["Not available", "Non-positive value"],
            default="Positive contextual value",
        ),
        index=series.index,
        dtype="string",
    )


def build_ops_review_board(
    primary_review: pd.DataFrame,
    secondary_review: pd.DataFrame,
    reverse_time_cases: pd.DataFrame,
    rules: dict | None = None,
) -> pd.DataFrame:
    """Create one sortable queue while keeping the three case classes distinct."""
    classification = _classification_rules(rules)
    priorities = classification["ops_priorities"]
    honored_definition = _honored_definition(rules)
    primary = pd.DataFrame(
        {
            "case_id": "PRIMARY-" + primary_review["booking_id"].astype("string"),
            "confidence_tier": primary_review["confidence_tier"],
            "case_class": classification["primary_case_class"],
            "recommended_action": (
                "Verify referral ownership in source CRM and confirm whether "
                "multiple prior referrers are valid."
            ),
            "priority": priorities["primary_review"]["label"],
            "priority_order": priorities["primary_review"]["order"],
            "booking_id": primary_review["booking_id"],
            "booking_timeline_at": primary_review["booking_timeline_at"],
            "booking_source_norm": primary_review["booking_source_norm"],
            "enquiry_source_norm": primary_review["enquiry_source_norm"],
            "lead_id": primary_review["booking_lead_id"],
            "lead_name": primary_review["booking_lead_name"],
            "referral_enquiry_id": primary_review["referral_enquiry_id"],
            "referral_submitted_at": primary_review["referral_submitted_at"],
            "referrer_user_id": primary_review["referrer_user_id"],
            "referrer_name": primary_review["referrer_name"],
            "prior_referral_count": primary_review["prior_referral_count"],
            "prior_referrer_count": primary_review["prior_referrer_count"],
            "days_between_referral_and_booking": primary_review[
                "days_between_referral_and_booking"
            ],
            "same_project": primary_review["same_project"],
            "timeline_ambiguity_flag": primary_review[
                "timeline_ambiguity_flag"
            ],
            "value_sanity_flag": _value_sanity(primary_review["agreement_value"]),
            "agreement_value": primary_review["agreement_value"],
            "review_reason": primary_review["review_reason"],
            "client_name": primary_review["client_name"],
            "test_demo_flag": primary_review["booking_test_demo_flag"],
            "identity_match_method": (
                rules["identity"]["primary_route"]["label"]
                if rules is not None
                else "Exact client + lead_id"
            ),
            "honored_definition_used": honored_definition,
        }
    )

    secondary = pd.DataFrame(
        {
            "case_id": "SECONDARY-"
            + secondary_review["booking_id"].astype("string"),
            "confidence_tier": secondary_review["confidence_tier"],
            "case_class": classification["secondary_case_class"],
            "recommended_action": (
                "Confirm the client and lead identity before any attribution decision."
            ),
            "priority": priorities["secondary_review"]["label"],
            "priority_order": priorities["secondary_review"]["order"],
            "booking_id": secondary_review["booking_id"],
            "booking_timeline_at": secondary_review["booking_timeline_at"],
            "booking_source_norm": secondary_review["booking_source_norm"],
            "enquiry_source_norm": secondary_review["enquiry_source_norm"],
            "lead_id": secondary_review["booking_lead_id"],
            "lead_name": secondary_review["booking_lead_name"],
            "referral_enquiry_id": secondary_review["referral_enquiry_id"],
            "referral_submitted_at": secondary_review["referral_submitted_at"],
            "referrer_user_id": secondary_review["referrer_user_id"],
            "referrer_name": secondary_review["referrer_name"],
            "prior_referral_count": pd.NA,
            "prior_referrer_count": pd.NA,
            "days_between_referral_and_booking": secondary_review[
                "days_between_referral_and_booking"
            ],
            "same_project": secondary_review["booking_project_id"].eq(
                secondary_review["referral_project_id"]
            ),
            "timeline_ambiguity_flag": False,
            "value_sanity_flag": _value_sanity(
                secondary_review["agreement_value"]
            ),
            "agreement_value": secondary_review["agreement_value"],
            "review_reason": secondary_review["review_reason"],
            "client_name": secondary_review["client_name"],
            "test_demo_flag": False,
            "identity_match_method": secondary_review["identity_rules_found"],
            "honored_definition_used": honored_definition,
        }
    )

    reverse = pd.DataFrame(
        {
            "case_id": "INTEGRITY-"
            + reverse_time_cases["referral_enquiry_id"].astype("string"),
            "confidence_tier": "Data Integrity",
            "case_class": classification["reverse_time_case_class"],
            "recommended_action": (
                "Validate referral and booking timestamps, then resolve the "
                "source-field disagreement."
            ),
            "priority": priorities["reverse_time"]["label"],
            "priority_order": priorities["reverse_time"]["order"],
            "booking_id": reverse_time_cases["booking_on_referral_id"],
            "booking_timeline_at": reverse_time_cases["booking_on_referral_at"],
            "booking_source_norm": reverse_time_cases[
                "booking_on_referral_source_norm"
            ],
            "enquiry_source_norm": reverse_time_cases["referral_source_norm"],
            "lead_id": reverse_time_cases["referral_lead_id"],
            "lead_name": reverse_time_cases["lead_name"],
            "referral_enquiry_id": reverse_time_cases["referral_enquiry_id"],
            "referral_submitted_at": reverse_time_cases[
                "referral_submitted_at"
            ],
            "referrer_user_id": reverse_time_cases["referrer_user_id"],
            "referrer_name": reverse_time_cases["referrer_name"],
            "prior_referral_count": pd.NA,
            "prior_referrer_count": pd.NA,
            "days_between_referral_and_booking": (
                reverse_time_cases["booking_on_referral_at"]
                - reverse_time_cases["referral_submitted_at"]
            ).dt.total_seconds()
            / 86400,
            "same_project": True,
            "timeline_ambiguity_flag": True,
            "value_sanity_flag": "Not available",
            "agreement_value": pd.NA,
            "review_reason": reverse_time_cases["issue_reason"],
            "client_name": reverse_time_cases["client_name"],
            "test_demo_flag": reverse_time_cases["referral_test_demo_flag"],
            "identity_match_method": "Same referral enquiry link",
            "honored_definition_used": honored_definition,
        }
    )

    # 对齐可空数值类型，保证不同 case class 拼接时类型稳定
    frames = [reverse, primary, secondary]
    for frame in frames:
        for column in [
            "prior_referral_count",
            "prior_referrer_count",
            "days_between_referral_and_booking",
            "agreement_value",
        ]:
            frame[column] = pd.to_numeric(
                frame[column],
                errors="coerce",
            ).astype("Float64")

    columns = list(primary.columns)
    return (
        pd.concat(
            [frame[columns] for frame in frames],
            ignore_index=True,
        )
        .sort_values(["priority_order", "case_class", "case_id"])
        .reset_index(drop=True)
    )
