"""Normalization and test/demo filtering."""

from __future__ import annotations

from typing import Any

import pandas as pd


def parse_datetime(series: pd.Series) -> pd.Series:
    """Parse mixed date formats; invalid values become NaT."""
    try:
        return pd.to_datetime(series, errors="coerce", format="mixed")
    except TypeError:
        return pd.to_datetime(series, errors="coerce")


def clean_id(series: pd.Series) -> pd.Series:
    """Normalize IDs as nullable strings without numeric round-trips."""
    return (
        series.astype("string")
        .str.strip()
        .replace({"": pd.NA, "NULL": pd.NA, "<NA>": pd.NA})
    )


def normalize_source(series: pd.Series) -> pd.Series:
    """Normalize source labels and keep missing values visible."""
    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace({"": "<NULL>", "NULL": "<NULL>"})
        .fillna("<NULL>")
    )


def has_test_demo_name(
    table: pd.DataFrame,
    fields: list[str],
    pattern: str,
) -> pd.Series:
    """Flag explicit test/demo tokens across configured name fields."""
    missing = [field for field in fields if field not in table.columns]
    if missing:
        raise ValueError(f"Test/demo fields are missing: {missing}")

    combined = table[fields[0]].fillna("").astype("string")
    for field in fields[1:]:
        combined = combined.str.cat(
            table[field].fillna("").astype("string"),
            sep=" ",
        )
    return combined.str.contains(pattern, case=False, regex=True, na=False)


def normalize_referrals(
    raw: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Add normalized referral fields used by every downstream module."""
    name_fields = rules["filters"]["test_demo_name_fields"]["referrals"]
    pattern = rules["filters"]["test_demo_pattern"]

    normalized = raw.assign(
        client_name=clean_id(raw["Client name"]),
        referral_enquiry_id=clean_id(raw["referral_enquiry_id"]),
        referral_submitted_at=parse_datetime(raw["referral_submitted_on"]),
        referral_source_norm=normalize_source(raw["source"]),
        referral_project_id=clean_id(raw["project_id"]),
        referral_lead_id=clean_id(raw["lead_id"]),
        referral_mobile_key=clean_id(raw["mobileNumber"]),
        referral_email_key=clean_id(raw["email"]),
        booking_on_referral_id=clean_id(raw["booking_on_referral_enquiry_id"]),
        booking_on_referral_at=parse_datetime(raw["booking_on_referral_date"]),
        booking_on_referral_source_norm=normalize_source(
            raw["booking_on_referral_source"]
        ),
        referral_test_demo_flag=has_test_demo_name(raw, name_fields, pattern),
    )

    if normalized["referral_enquiry_id"].duplicated().any():
        duplicate_count = int(normalized["referral_enquiry_id"].duplicated().sum())
        raise ValueError(
            "referral_enquiry_id is not unique at the expected grain; "
            f"found {duplicate_count} duplicate rows."
        )
    return normalized


def normalize_bookings(
    raw: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Add normalized booking fields and the strict honored flag."""
    name_fields = rules["filters"]["test_demo_name_fields"]["bookings"]
    pattern = rules["filters"]["test_demo_pattern"]

    normalized = raw.assign(
        client_name=clean_id(raw["Client name"]),
        booking_id=clean_id(raw["booking_id"]),
        enquiry_id=clean_id(raw["enquiry_id"]),
        booking_date_at=parse_datetime(raw["bookingDate"]),
        booking_created_at=parse_datetime(raw["booking_created_on"]),
        booking_source_norm=normalize_source(raw["booking_source"]),
        enquiry_source_norm=normalize_source(raw["enquiry_source"]),
        booking_project_id=clean_id(raw["project_id"]),
        booking_lead_id=clean_id(raw["lead_id"]),
        booking_mobile_key=clean_id(raw["mobileNumber"]),
        booking_email_key=clean_id(raw["email"]),
        agreement_value=pd.to_numeric(raw["agreementValue"], errors="coerce"),
        booking_test_demo_flag=has_test_demo_name(raw, name_fields, pattern),
    )
    # 规则表决定 booking 时间的 fallback 顺序和 honored source。
    timeline_fields = rules["time"]["booking_fallback_order"]
    missing_timeline_fields = [
        field for field in timeline_fields if field not in normalized.columns
    ]
    if missing_timeline_fields:
        raise ValueError(
            "Configured booking timeline fields are unavailable after normalization: "
            f"{missing_timeline_fields}"
        )

    booking_timeline = normalized[timeline_fields[0]]
    for field in timeline_fields[1:]:
        booking_timeline = booking_timeline.fillna(normalized[field])

    strict_rule = rules["honored"]["strict"]
    source_field = strict_rule["normalized_field"]
    if source_field not in normalized.columns:
        raise ValueError(
            f"Configured honored source field is unavailable: {source_field}"
        )
    normalized = normalized.assign(
        booking_timeline_at=booking_timeline,
        honored_strict=normalized[source_field].isin(
            strict_rule["accepted_values"]
        ),
    )

    if normalized["booking_id"].duplicated().any():
        duplicate_count = int(normalized["booking_id"].duplicated().sum())
        raise ValueError(
            "booking_id is not unique at the expected grain; "
            f"found {duplicate_count} duplicate rows."
        )
    return normalized


def filter_test_demo(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    enabled: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply the explicit test/demo filter and reconcile row counts."""
    if enabled:
        filtered_referrals = referrals.loc[~referrals["referral_test_demo_flag"]]
        filtered_bookings = bookings.loc[~bookings["booking_test_demo_flag"]]
    else:
        filtered_referrals = referrals
        filtered_bookings = bookings

    summary = pd.DataFrame(
        [
            {
                "dataset": "Referral submissions",
                "before_filter": len(referrals),
                "test_demo_removed": int(
                    referrals["referral_test_demo_flag"].sum()
                )
                if enabled
                else 0,
                "after_filter": len(filtered_referrals),
            },
            {
                "dataset": "Bookings",
                "before_filter": len(bookings),
                "test_demo_removed": int(
                    bookings["booking_test_demo_flag"].sum()
                )
                if enabled
                else 0,
                "after_filter": len(filtered_bookings),
            },
        ]
    )
    return filtered_referrals, filtered_bookings, summary
