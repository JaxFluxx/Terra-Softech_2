"""Multi-referrer policy simulations and booking-warning decisions."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .matching import select_latest_prior_referral


def _window_label(window_days: int | None) -> str:
    """Return a stable reporting label for a configured window."""
    return "Unlimited" if window_days is None else f"{window_days} days"


def _pairs_in_window(
    time_valid_pairs: pd.DataFrame,
    window_days: int | None,
) -> pd.DataFrame:
    """Keep only the time-valid pairs included in one scenario."""
    if window_days is None:
        return time_valid_pairs
    return time_valid_pairs.loc[
        time_valid_pairs["days_between_referral_and_booking"].le(window_days)
    ]


def _policy_decision_for_booking(
    booking_pairs: pd.DataFrame,
    policy: dict[str, Any],
    manual_referrer_threshold: int,
) -> dict[str, Any]:
    """Apply one provisional ownership policy to a single booking."""
    ordered = booking_pairs.sort_values(
        ["referral_submitted_at", "referral_enquiry_id"]
    )
    latest = ordered.iloc[-1]
    first = ordered.iloc[0]
    same_project_pairs = ordered.loc[
        ordered["booking_project_id"].eq(ordered["referral_project_id"])
    ]
    prior_referrer_count = int(ordered["referrer_user_id"].nunique(dropna=True))
    mode = policy["mode"]

    auto_assignable = True
    manual_reason = ""
    candidate = latest
    decision = "Auto assign latest prior referrer"
    if mode == "first":
        candidate = first
        decision = "Auto assign first prior referrer"
    elif mode == "manual_when_multiple":
        if prior_referrer_count >= manual_referrer_threshold:
            auto_assignable = False
            manual_reason = "Multiple prior referrers require manual ownership review"
            decision = "Manual ownership review"
        else:
            decision = "Auto assign latest prior referrer"
    elif mode == "same_project_latest":
        if same_project_pairs.empty:
            auto_assignable = False
            manual_reason = "No same-project prior referral for automatic owner hint"
            decision = "Manual ownership review"
        else:
            candidate = same_project_pairs.iloc[-1]
            decision = "Auto assign latest same-project referrer"
    elif mode != "latest":
        raise ValueError(f"Unsupported policy mode: {mode}")

    return {
        "booking_id": latest["booking_id"],
        "prior_referral_count": int(ordered["referral_enquiry_id"].nunique()),
        "prior_referrer_count": prior_referrer_count,
        "same_project_candidate_available": not same_project_pairs.empty,
        "auto_assignable": auto_assignable,
        "manual_review_required": not auto_assignable,
        "policy_decision": decision,
        "manual_reason": manual_reason,
        "reference_referral_enquiry_id": latest["referral_enquiry_id"],
        "reference_referrer_user_id": latest["referrer_user_id"],
        "auto_owner_referral_enquiry_id": (
            candidate["referral_enquiry_id"] if auto_assignable else pd.NA
        ),
        "auto_owner_referrer_user_id": (
            candidate["referrer_user_id"] if auto_assignable else pd.NA
        ),
    }


def apply_ownership_policy(
    time_valid_pairs: pd.DataFrame,
    policy: dict[str, Any],
    manual_referrer_threshold: int,
    window_days: int | None = None,
) -> pd.DataFrame:
    """Return one policy outcome per eligible booking for one scenario."""
    scenario_pairs = _pairs_in_window(time_valid_pairs, window_days)
    if scenario_pairs.empty:
        return pd.DataFrame(
            columns=[
                "booking_id",
                "prior_referral_count",
                "prior_referrer_count",
                "same_project_candidate_available",
                "auto_assignable",
                "manual_review_required",
                "policy_decision",
                "manual_reason",
                "reference_referral_enquiry_id",
                "reference_referrer_user_id",
                "auto_owner_referral_enquiry_id",
                "auto_owner_referrer_user_id",
            ]
        )
    rows = [
        _policy_decision_for_booking(group, policy, manual_referrer_threshold)
        for _, group in scenario_pairs.groupby("booking_id", sort=True)
    ]
    return pd.DataFrame(rows)


def _window_review_sets(
    time_valid_pairs: pd.DataFrame,
    window_days: int | None,
) -> tuple[pd.DataFrame, set[str], set[str]]:
    """Recompute eligible, review, and Tier B-like booking sets by window."""
    matches = select_latest_prior_referral(
        time_valid_pairs,
        max_window_days=window_days,
        latest_prior_referral=True,
    )
    review = matches.loc[~matches["honored_strict"]]
    review_ids = set(review["booking_id"].dropna().astype("string"))
    tier_b_ids = set(
        review.loc[
            review["multiple_referrer_flag"] | review["timeline_ambiguity_flag"],
            "booking_id",
        ]
        .dropna()
        .astype("string")
    )
    return matches, review_ids, tier_b_ids


def _format_booking_ids(booking_ids: set[str]) -> str:
    """Keep scenario case IDs readable and numerically ordered in CSV output."""
    def sort_key(booking_id: str) -> tuple[int, int | str]:
        text = str(booking_id)
        return (0, int(text)) if text.isdigit() else (1, text)

    return ", ".join(sorted(booking_ids, key=sort_key))


def _policy_summary_rows(
    time_valid_pairs: pd.DataFrame,
    rules: dict[str, Any],
    window_days: int | None,
) -> list[dict[str, Any]]:
    """Summarize every configured ownership policy under one window."""
    policy_settings = rules["process"]["multi_referrer"]
    threshold = int(policy_settings["manual_referrer_threshold"])
    matches, review_ids, tier_b_ids = _window_review_sets(time_valid_pairs, window_days)
    _, _, baseline_tier_b_ids = _window_review_sets(time_valid_pairs, None)
    eligible_booking_ids = set(matches["booking_id"].dropna().astype("string"))
    baseline_tier_b_in_window_ids = baseline_tier_b_ids & eligible_booking_ids
    rows = []
    for policy in policy_settings["policies"]:
        outcomes = apply_ownership_policy(
            time_valid_pairs,
            policy,
            manual_referrer_threshold=threshold,
            window_days=window_days,
        )
        outcome_ids = outcomes["booking_id"].astype("string")
        manual_mask = outcomes["manual_review_required"].fillna(False)
        auto_mask = outcomes["auto_assignable"].fillna(False)
        rows.append(
            {
                "policy_id": policy["policy_id"],
                "policy_label": policy["label"],
                "policy_mode": policy["mode"],
                "attribution_window": _window_label(window_days),
                "window_days": window_days,
                "eligible_bookings": int(matches["booking_id"].nunique()),
                "primary_review_candidates": len(review_ids),
                "primary_review_in_window_count": len(review_ids),
                "primary_review_in_window_booking_ids": _format_booking_ids(
                    review_ids
                ),
                "auto_assignable_count": int(auto_mask.sum()),
                "manual_review_count": int(manual_mask.sum()),
                "tier_b_auto_owner_count": int(
                    outcome_ids.loc[auto_mask].isin(tier_b_ids).sum()
                ),
                "tier_b_manual_review_count": int(
                    outcome_ids.loc[manual_mask].isin(tier_b_ids).sum()
                ),
                "baseline_tier_b_cases_in_window_count": len(
                    baseline_tier_b_in_window_ids
                ),
                "baseline_tier_b_cases_in_window_booking_ids": _format_booking_ids(
                    baseline_tier_b_in_window_ids
                ),
                "window_recomputed_tier_b_count": len(tier_b_ids),
                "window_recomputed_tier_b_booking_ids": _format_booking_ids(
                    tier_b_ids
                ),
                "recommended_policy": policy["policy_id"]
                == policy_settings["recommended_policy_id"],
                "notes": policy["notes"],
            }
        )
    return rows


def build_multi_referrer_policy_sensitivity(
    time_valid_pairs: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Compare ownership policies on the unlimited batch-analysis view."""
    return pd.DataFrame(_policy_summary_rows(time_valid_pairs, rules, None))


def build_multi_referrer_policy_case_matrix(
    time_valid_pairs: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Make every unlimited-window policy outcome traceable by booking."""
    policy_settings = rules["process"]["multi_referrer"]
    threshold = int(policy_settings["manual_referrer_threshold"])
    pair_context = time_valid_pairs.assign(
        same_project_pair=lambda frame: frame["booking_project_id"].eq(
            frame["referral_project_id"]
        )
    )
    reference = (
        pair_context.groupby("booking_id", as_index=False)
        .agg(
            earliest_days_between_referral_and_booking=(
                "days_between_referral_and_booking",
                "min",
            ),
            latest_days_between_referral_and_booking=(
                "days_between_referral_and_booking",
                "max",
            ),
            same_project_prior_referral_available=("same_project_pair", "any"),
        )
        .sort_values("booking_id")
    )
    rows = []
    for policy in policy_settings["policies"]:
        outcomes = apply_ownership_policy(
            time_valid_pairs,
            policy,
            manual_referrer_threshold=threshold,
        )
        matrix = reference.merge(outcomes, on="booking_id", how="inner")
        matrix = matrix.assign(
            policy_id=policy["policy_id"],
            policy_label=policy["label"],
            recommended_policy=(
                policy["policy_id"] == policy_settings["recommended_policy_id"]
            ),
            owner_result=lambda frame: frame["auto_owner_referrer_user_id"].fillna(
                "MANUAL_REVIEW"
            ),
        )
        rows.append(matrix)
    return pd.concat(rows, ignore_index=True).loc[
        :,
        [
            "policy_id",
            "policy_label",
            "recommended_policy",
            "booking_id",
            "prior_referral_count",
            "prior_referrer_count",
            "earliest_days_between_referral_and_booking",
            "latest_days_between_referral_and_booking",
            "same_project_prior_referral_available",
            "reference_referral_enquiry_id",
            "reference_referrer_user_id",
            "auto_assignable",
            "manual_review_required",
            "owner_result",
            "policy_decision",
            "manual_reason",
        ],
    ]


def build_process_window_and_policy_sensitivity(
    time_valid_pairs: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Show how pilot windows and policy choices affect the review path."""
    windows = [*rules["process"]["sensitivity_windows_days"], None]
    rows = [
        row
        for window_days in windows
        for row in _policy_summary_rows(time_valid_pairs, rules, window_days)
    ]
    return pd.DataFrame(rows)


def evaluate_open_referral_warning(
    booking_source_proposed: str,
    prior_referral_count: int,
    prior_referrer_count: int,
    same_project_any: bool,
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate the Product warning rule without changing source data."""
    settings = rules["process"]["booking_warning"]
    accepted_sources = {
        source.strip().upper()
        for source in settings["trigger_when_source_not_in"]
    }
    source = (booking_source_proposed or "").strip().upper()
    result = {
        "warning_shown": False,
        "warning_severity": "None",
        "action": settings["no_prior_referral_action"],
        "override_reason_required": False,
        "manual_review_required": False,
        "decision": "Proceed",
        "window_days": int(settings["window_days"]),
    }
    if source in accepted_sources:
        result["action"] = "No warning; booking source is already REFERRAL"
        return result
    if prior_referral_count <= 0:
        return result
    if not same_project_any:
        return {
            **result,
            "warning_shown": True,
            "warning_severity": "Low",
            "action": settings["cross_project_only_action"],
            "decision": "Proceed and log",
        }
    if prior_referrer_count >= int(
        rules["process"]["multi_referrer"]["manual_referrer_threshold"]
    ):
        return {
            **result,
            "warning_shown": True,
            "warning_severity": "High",
            "action": settings["multiple_same_project_action"],
            "override_reason_required": True,
            "manual_review_required": True,
            "decision": "Escalate",
        }
    return {
        **result,
        "warning_shown": True,
        "warning_severity": "Medium",
        "action": settings["single_same_project_action"],
        "decision": "Proceed with warning",
    }


def build_warning_decision_table(rules: dict[str, Any]) -> pd.DataFrame:
    """Make the configured Product behavior readable in the notebook."""
    scenarios = [
        ("No prior referral", "DIRECT", 0, 0, False),
        ("One same-project referrer", "DIRECT", 1, 1, True),
        ("Multiple same-project referrers", "DIRECT", 2, 2, True),
        ("Cross-project referrals only", "DIRECT", 1, 1, False),
    ]
    rows = []
    for scenario, source, referrals, referrers, same_project in scenarios:
        outcome = evaluate_open_referral_warning(
            source,
            referrals,
            referrers,
            same_project,
            rules,
        )
        rows.append({"scenario": scenario, **outcome})
    return pd.DataFrame(rows)
