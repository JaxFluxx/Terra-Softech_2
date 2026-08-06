"""Primary, same-enquiry, and secondary identity matching."""

from __future__ import annotations

import numpy as np
import pandas as pd


def build_time_valid_pairs(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    identity_rule: dict | None = None,
    allow_referral_on_booking_date: bool = True,
) -> pd.DataFrame:
    """Create exact client + lead_id pairs that pass the time-order gate."""
    referral_columns = [
        "client_name",
        "referral_enquiry_id",
        "referral_submitted_at",
        "referral_enquiry_status",
        "stage",
        "referralSource",
        "referralCode",
        "sourcePlatform",
        "referral_project_id",
        "projectName",
        "referrer_user_id",
        "referrer_name",
        "referrer_user_type",
        "referral_lead_id",
        "lead_name",
        "lead_hash_id",
        "referral_mobile_key",
        "referral_email_key",
        "referral_test_demo_flag",
    ]
    booking_columns = [
        "client_name",
        "booking_id",
        "booking_crm_id",
        "booking_timeline_at",
        "booking_date_at",
        "booking_created_at",
        "bookingStatus",
        "booking_source_norm",
        "enquiry_id",
        "enquiry_source_norm",
        "booking_lead_id",
        "lead_name",
        "lead_hash_id",
        "booking_project_id",
        "projectName",
        "agreement_value",
        "honored_strict",
        "booking_test_demo_flag",
    ]

    referral_base = referrals.loc[
        referrals["referral_lead_id"].notna()
        & referrals["referral_submitted_at"].notna(),
        referral_columns,
    ].rename(
        columns={
            "projectName": "referral_project_name",
            "lead_name": "referral_lead_name",
            "lead_hash_id": "referral_lead_hash_id",
        }
    )
    booking_base = bookings.loc[
        bookings["booking_lead_id"].notna()
        & bookings["booking_timeline_at"].notna(),
        booking_columns,
    ].rename(
        columns={
            "lead_name": "booking_lead_name",
            "lead_hash_id": "booking_lead_hash_id",
            "projectName": "booking_project_name",
        }
    )

    identity_rule = identity_rule or {
        "booking_fields": ["client_name", "booking_lead_id"],
        "referral_fields": ["client_name", "referral_lead_id"],
    }
    booking_fields = identity_rule["booking_fields"]
    referral_fields = identity_rule["referral_fields"]
    if len(booking_fields) != len(referral_fields):
        raise ValueError("Primary identity fields must have equal lengths.")

    pairs = booking_base.merge(
        referral_base,
        left_on=booking_fields,
        right_on=referral_fields,
        how="inner",
        validate="many_to_many",
    )
    time_valid = (
        pairs["referral_submitted_at"].le(pairs["booking_timeline_at"])
        if allow_referral_on_booking_date
        else pairs["referral_submitted_at"].lt(pairs["booking_timeline_at"])
    )
    return pairs.loc[time_valid].assign(
        days_between_referral_and_booking=lambda frame: (
            frame["booking_timeline_at"] - frame["referral_submitted_at"]
        ).dt.total_seconds()
        / 86400
    )


def select_latest_prior_referral(
    time_valid_pairs: pd.DataFrame,
    max_window_days: int | None = None,
    latest_prior_referral: bool = True,
) -> pd.DataFrame:
    """Select one latest eligible referral per booking."""
    eligible = time_valid_pairs
    if max_window_days is not None:
        eligible = eligible.loc[
            eligible["days_between_referral_and_booking"].le(max_window_days)
        ]

    counts = (
        eligible.groupby("booking_id")
        .agg(
            prior_referral_count=("referral_enquiry_id", "nunique"),
            prior_referrer_count=("referrer_user_id", "nunique"),
            prior_project_count=("referral_project_id", "nunique"),
            earliest_prior_referral_at=("referral_submitted_at", "min"),
            latest_prior_referral_at=("referral_submitted_at", "max"),
        )
        .reset_index()
    )
    selected = (
        eligible.sort_values(
            ["booking_id", "referral_submitted_at", "referral_enquiry_id"]
        )
        .drop_duplicates(
            subset=["booking_id"],
            keep="last" if latest_prior_referral else "first",
        )
        .merge(counts, on="booking_id", how="left", validate="one_to_one")
    )

    return selected.assign(
        same_project=lambda frame: frame["booking_project_id"].eq(
            frame["referral_project_id"]
        ),
        multiple_referral_flag=lambda frame: frame["prior_referral_count"].gt(1),
        multiple_referrer_flag=lambda frame: frame["prior_referrer_count"].gt(1),
        timeline_ambiguity_flag=lambda frame: (
            frame["booking_created_at"].notna()
            & frame["referral_submitted_at"].gt(frame["booking_created_at"])
            & frame["referral_submitted_at"].le(frame["booking_timeline_at"])
        ),
    )


def analyze_same_enquiry(
    referrals: pd.DataFrame,
    accepted_sources: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Separate valid same-enquiry conversions from reverse-time data issues."""
    accepted_sources = accepted_sources or ["REFERRAL"]
    same_enquiry = referrals.loc[
        referrals["booking_on_referral_id"].notna()
    ].assign(
        same_enquiry_time_status=lambda frame: np.select(
            [
                frame["referral_submitted_at"].isna()
                | frame["booking_on_referral_at"].isna(),
                frame["booking_on_referral_at"].lt(
                    frame["referral_submitted_at"]
                ),
            ],
            ["Missing Date", "Reverse Time"],
            default="Time Valid",
        ),
        same_enquiry_honored_strict=lambda frame: frame[
            "booking_on_referral_source_norm"
        ].isin(accepted_sources),
        source_disagreement_flag=lambda frame: frame[
            "referral_source_norm"
        ].isin(accepted_sources)
        & ~frame["booking_on_referral_source_norm"].isin(accepted_sources),
    )

    summary = (
        same_enquiry.groupby(
            ["same_enquiry_time_status", "booking_on_referral_source_norm"],
            dropna=False,
        )
        .agg(
            referral_enquiry_rows=("referral_enquiry_id", "size"),
            unique_leads=("referral_lead_id", "nunique"),
            test_demo_rows=("referral_test_demo_flag", "sum"),
        )
        .reset_index()
        .sort_values(
            ["same_enquiry_time_status", "booking_on_referral_source_norm"]
        )
    )

    reverse_time = same_enquiry.loc[
        same_enquiry["same_enquiry_time_status"].eq("Reverse Time")
        & same_enquiry["source_disagreement_flag"]
    ].assign(
        review_class="Data Integrity - Reverse Time",
        issue_reason=(
            "Booking date is earlier than referral submission; "
            "source mismatch cannot be scored as bypass."
        ),
    )
    time_valid = same_enquiry.loc[
        same_enquiry["same_enquiry_time_status"].eq("Time Valid")
    ].assign(
        review_class=lambda frame: np.where(
            frame["same_enquiry_honored_strict"],
            "Time Valid - Strictly Honored",
            "Time Valid - Strict Source Review",
        )
    )
    return same_enquiry, summary, reverse_time, time_valid


def build_secondary_identity_matches(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    referral_key: str,
    booking_key: str,
    rule_name: str,
    excluded_booking_ids: set[str],
    allow_referral_on_booking_date: bool = True,
) -> pd.DataFrame:
    """Build exact encrypted-identity matches outside the primary lead route."""
    referral_identity = referrals.loc[
        referrals[referral_key].notna()
        & referrals["referral_submitted_at"].notna(),
        [
            "client_name",
            referral_key,
            "referral_enquiry_id",
            "referral_submitted_at",
            "referral_lead_id",
            "lead_name",
            "referrer_user_id",
            "referrer_name",
            "referral_project_id",
            "projectName",
        ],
    ].rename(
        columns={
            referral_key: "identity_key",
            "lead_name": "referral_lead_name",
            "projectName": "referral_project_name",
        }
    )
    booking_identity = bookings.loc[
        bookings[booking_key].notna()
        & bookings["booking_timeline_at"].notna()
        & ~bookings["booking_id"].isin(excluded_booking_ids),
        [
            "client_name",
            booking_key,
            "booking_id",
            "booking_timeline_at",
            "booking_source_norm",
            "enquiry_source_norm",
            "booking_lead_id",
            "lead_name",
            "booking_project_id",
            "projectName",
            "agreement_value",
            "honored_strict",
        ],
    ].rename(
        columns={
            booking_key: "identity_key",
            "lead_name": "booking_lead_name",
            "projectName": "booking_project_name",
        }
    )

    candidates = booking_identity.merge(
        referral_identity,
        on=["client_name", "identity_key"],
        how="inner",
        validate="many_to_many",
    )
    time_valid = (
        candidates["referral_submitted_at"].le(candidates["booking_timeline_at"])
        if allow_referral_on_booking_date
        else candidates["referral_submitted_at"].lt(candidates["booking_timeline_at"])
    )
    candidates = candidates.loc[time_valid].assign(
        identity_rule=rule_name,
        days_between_referral_and_booking=lambda frame: (
            frame["booking_timeline_at"] - frame["referral_submitted_at"]
        ).dt.total_seconds()
        / 86400,
    )

    referral_cardinality = (
        referral_identity.groupby(["client_name", "identity_key"])[
            "referral_lead_id"
        ]
        .nunique(dropna=True)
        .rename("referral_leads_per_identity_key")
        .reset_index()
    )
    booking_cardinality = (
        booking_identity.groupby(["client_name", "identity_key"])[
            "booking_lead_id"
        ]
        .nunique(dropna=True)
        .rename("booking_leads_per_identity_key")
        .reset_index()
    )

    return (
        candidates.sort_values(
            ["booking_id", "referral_submitted_at", "referral_enquiry_id"]
        )
        .drop_duplicates(subset=["booking_id"], keep="last")
        .merge(
            referral_cardinality,
            on=["client_name", "identity_key"],
            how="left",
        )
        .merge(
            booking_cardinality,
            on=["client_name", "identity_key"],
            how="left",
        )
        .assign(
            identity_collision_flag=lambda frame: (
                frame["referral_leads_per_identity_key"].gt(1)
                | frame["booking_leads_per_identity_key"].gt(1)
            )
        )
    )


def combine_secondary_routes(
    *route_matches: pd.DataFrame,
) -> pd.DataFrame:
    """Combine exact mobile/email routes into one row per booking."""
    combined = pd.concat(route_matches, ignore_index=True)
    if combined.empty:
        return combined

    rule_labels = (
        combined.groupby("booking_id")["identity_rule"]
        .agg(lambda values: " + ".join(sorted(set(values))))
        .rename("identity_rules_found")
        .reset_index()
    )
    return (
        combined.sort_values(
            ["booking_id", "referral_submitted_at", "identity_rule"]
        )
        .drop_duplicates(subset=["booking_id"], keep="last")
        .merge(rule_labels, on="booking_id", how="left", validate="one_to_one")
    )
