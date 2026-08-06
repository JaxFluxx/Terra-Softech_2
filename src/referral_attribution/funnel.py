"""Lifecycle funnel and decision-useful diagnostics."""

from __future__ import annotations

import pandas as pd

from .matching import select_latest_prior_referral


def build_lifecycle_funnel(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    primary_matches: pd.DataFrame,
    reverse_time_count: int,
    identity_rule: dict | None = None,
    honored_label: str = "Booking source recorded as REFERRAL",
) -> pd.DataFrame:
    """Build the required funnel with explicit grains and denominators."""
    identity_rule = identity_rule or {
        "booking_fields": ["client_name", "booking_lead_id"],
        "referral_fields": ["client_name", "referral_lead_id"],
        "label": "Exact client + lead_id",
    }
    booking_identity_fields = identity_rule["booking_fields"]
    referral_identity_fields = identity_rule["referral_fields"]
    identity_label = identity_rule["label"]
    booking_keys = bookings.loc[
        bookings["booking_lead_id"].notna(),
        booking_identity_fields,
    ].drop_duplicates()
    referral_identity_overlap = referrals.merge(
        booking_keys,
        left_on=referral_identity_fields,
        right_on=booking_identity_fields,
        how="inner",
    )
    referral_keys = referrals.loc[
        referrals["referral_lead_id"].notna(),
        referral_identity_fields,
    ].drop_duplicates()
    booking_identity_overlap = bookings.merge(
        referral_keys,
        left_on=booking_identity_fields,
        right_on=referral_identity_fields,
        how="inner",
    )

    filtered_referrals = len(referrals)
    identity_referrals = referral_identity_overlap["referral_enquiry_id"].nunique()
    identity_bookings = booking_identity_overlap["booking_id"].nunique()
    eligible_bookings = primary_matches["booking_id"].nunique()
    strict_honored = primary_matches.loc[
        primary_matches["honored_strict"], "booking_id"
    ].nunique()
    review_candidates = primary_matches.loc[
        ~primary_matches["honored_strict"], "booking_id"
    ].nunique()

    rows = [
        {
            "stage_order": 1,
            "stage": "Referral submissions after test/demo filtering",
            "grain": "Referral enquiry",
            "count": filtered_referrals,
            "denominator": "Filtered referral submissions",
            "denominator_count": filtered_referrals,
            "rate": 1.0,
            "included_in_primary_funnel": True,
        },
        {
            "stage_order": 2,
            "stage": (
                "Referral submissions sharing " + identity_label + " with a booking"
            ),
            "grain": "Referral enquiry",
            "count": identity_referrals,
            "denominator": "Filtered referral submissions",
            "denominator_count": filtered_referrals,
            "rate": identity_referrals / filtered_referrals,
            "included_in_primary_funnel": True,
        },
        {
            "stage_order": 3,
            "stage": (
                "Bookings sharing " + identity_label + " with a referral submission"
            ),
            "grain": "Booking",
            "count": identity_bookings,
            "denominator": "Filtered bookings",
            "denominator_count": len(bookings),
            "rate": identity_bookings / len(bookings),
            "included_in_primary_funnel": True,
        },
        {
            "stage_order": 4,
            "stage": "Bookings with at least one time-valid prior referral",
            "grain": "Booking",
            "count": eligible_bookings,
            "denominator": "Bookings sharing " + identity_label,
            "denominator_count": identity_bookings,
            "rate": eligible_bookings / identity_bookings,
            "included_in_primary_funnel": True,
        },
        {
            "stage_order": 5,
            "stage": "Honored bookings: " + honored_label,
            "grain": "Booking",
            "count": strict_honored,
            "denominator": "Bookings with time-valid prior referral",
            "denominator_count": eligible_bookings,
            "rate": strict_honored / eligible_bookings,
            "included_in_primary_funnel": True,
        },
        {
            "stage_order": 6,
            "stage": "Primary review candidates",
            "grain": "Booking",
            "count": review_candidates,
            "denominator": "Bookings with time-valid prior referral",
            "denominator_count": eligible_bookings,
            "rate": review_candidates / eligible_bookings,
            "included_in_primary_funnel": True,
        },
        {
            "stage_order": 7,
            "stage": "Reverse-time source disagreements (outside funnel)",
            "grain": "Referral enquiry",
            "count": reverse_time_count,
            "denominator": "Not a bypass denominator",
            "denominator_count": pd.NA,
            "rate": pd.NA,
            "included_in_primary_funnel": False,
        },
    ]
    return pd.DataFrame(rows)


def build_project_diagnostic(primary_matches: pd.DataFrame) -> pd.DataFrame:
    """Compare same-project and cross-project evidence among eligible matches."""
    labeled = primary_matches.assign(
        project_relationship=primary_matches["same_project"].map(
            {True: "Same project", False: "Cross project"}
        )
    )
    total = labeled["booking_id"].nunique()
    return (
        labeled.groupby("project_relationship", dropna=False)
        .agg(
            matched_bookings=("booking_id", "nunique"),
            strict_honored_bookings=("honored_strict", "sum"),
        )
        .reset_index()
        .assign(
            primary_review_candidates=lambda frame: (
                frame["matched_bookings"] - frame["strict_honored_bookings"]
            ),
            share_of_eligible_bookings=lambda frame: frame[
                "matched_bookings"
            ]
            / total,
        )
    )


def build_source_diagnostic(
    bookings: pd.DataFrame,
    primary_matches: pd.DataFrame,
) -> pd.DataFrame:
    """Show source distributions for the full booking base and eligible matches."""
    all_bookings = (
        bookings.groupby("booking_source_norm", dropna=False)
        .agg(booking_count=("booking_id", "nunique"))
        .reset_index()
        .assign(
            cohort="All filtered bookings",
            share=lambda frame: frame["booking_count"]
            / frame["booking_count"].sum(),
        )
    )
    matched = (
        primary_matches.groupby("booking_source_norm", dropna=False)
        .agg(booking_count=("booking_id", "nunique"))
        .reset_index()
        .assign(
            cohort="Bookings with time-valid prior referral",
            share=lambda frame: frame["booking_count"]
            / frame["booking_count"].sum(),
        )
    )
    return pd.concat([all_bookings, matched], ignore_index=True)[
        ["cohort", "booking_source_norm", "booking_count", "share"]
    ]


def build_multi_referrer_diagnostic(
    primary_matches: pd.DataFrame,
) -> pd.DataFrame:
    """Quantify the ambiguity created by multiple prior referrers."""
    labeled = primary_matches.assign(
        referrer_group=primary_matches["multiple_referrer_flag"].map(
            {False: "Single prior referrer", True: "Multiple prior referrers"}
        )
    )
    total = labeled["booking_id"].nunique()
    return (
        labeled.groupby("referrer_group", dropna=False)
        .agg(
            matched_bookings=("booking_id", "nunique"),
            strict_honored_bookings=("honored_strict", "sum"),
            median_prior_referrers=("prior_referrer_count", "median"),
        )
        .reset_index()
        .assign(
            primary_review_candidates=lambda frame: (
                frame["matched_bookings"] - frame["strict_honored_bookings"]
            ),
            share_of_eligible_bookings=lambda frame: frame[
                "matched_bookings"
            ]
            / total,
        )
    )


def build_window_sensitivity(
    time_valid_pairs: pd.DataFrame,
    windows: list[int],
    cohort: str = "After test/demo filter",
    latest_prior_referral: bool = True,
) -> pd.DataFrame:
    """Recompute strict outcomes under each labeled time window."""
    rows = []
    for window in [*windows, None]:
        matches = select_latest_prior_referral(
            time_valid_pairs,
            max_window_days=window,
            latest_prior_referral=latest_prior_referral,
        )
        rows.append(
            {
                "cohort": cohort,
                "attribution_window": (
                    "No limit" if window is None else f"{window} days"
                ),
                "window_days": window,
                "matched_bookings": matches["booking_id"].nunique(),
                "strict_honored_bookings": matches.loc[
                    matches["honored_strict"], "booking_id"
                ].nunique(),
                "primary_review_candidates": matches.loc[
                    ~matches["honored_strict"], "booking_id"
                ].nunique(),
            }
        )
    return pd.DataFrame(rows)
