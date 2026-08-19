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


def has_configured_test_demo_signal(
    table: pd.DataFrame,
    signals: list[dict[str, Any]],
) -> pd.Series:
    """Flag only explicit strong test/demo signals defined in JSON."""
    flagged = pd.Series(False, index=table.index, dtype="bool")
    for signal in signals:
        field = signal.get("field")
        match_type = signal.get("match")
        if not field or not match_type:
            raise ValueError("Each strong test/demo signal needs field and match.")
        if field not in table.columns:
            raise ValueError(
                f"Configured strong test/demo field is unavailable: {field}"
            )

        values = table[field].astype("string").fillna("").str.strip()
        if match_type == "regex":
            pattern = signal.get("pattern")
            if not pattern:
                raise ValueError(f"Regex signal for {field} is missing a pattern.")
            matched = values.str.contains(pattern, case=False, regex=True, na=False)
        elif match_type == "exact":
            expected = signal.get("values", [])
            if not expected:
                raise ValueError(f"Exact signal for {field} is missing values.")
            matched = values.str.upper().isin(
                {str(value).strip().upper() for value in expected}
            )
        else:
            raise ValueError(
                f"Unsupported strong test/demo match type for {field}: {match_type}"
            )
        flagged = flagged | matched
    return flagged


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
    )
    strong_signals = rules["filters"].get("strong_test_demo_signals", {}).get(
        "referrals", []
    )
    strong_enabled = rules["filters"].get("strong_test_demo_enabled", False)
    normalized = normalized.assign(
        referral_test_demo_name_flag=has_test_demo_name(raw, name_fields, pattern),
        # Keep strong signals as audit fields; the JSON switch controls exclusion.
        referral_test_demo_strong_signal_flag=has_configured_test_demo_signal(
            normalized, strong_signals
        ),
    ).assign(
        referral_test_demo_flag=lambda frame: (
            frame["referral_test_demo_name_flag"]
            | (
                frame["referral_test_demo_strong_signal_flag"]
                if strong_enabled
                else False
            )
        )
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
        booking_crm_id=clean_id(raw["booking_crm_id"]),
        enquiry_id=clean_id(raw["enquiry_id"]),
        booking_date_at=parse_datetime(raw["bookingDate"]),
        booking_created_at=parse_datetime(raw["booking_created_on"]),
        booking_source_norm=normalize_source(raw["booking_source"]),
        enquiry_source_norm=normalize_source(raw["enquiry_source"]),
        booking_project_id=clean_id(raw["project_id"]),
        booking_unit_number=clean_id(raw["unitNumber"]),
        booking_lead_id=clean_id(raw["lead_id"]),
        booking_mobile_key=clean_id(raw["mobileNumber"]),
        booking_email_key=clean_id(raw["email"]),
        agreement_value=pd.to_numeric(raw["agreementValue"], errors="coerce"),
    )
    strong_signals = rules["filters"].get("strong_test_demo_signals", {}).get(
        "bookings", []
    )
    strong_enabled = rules["filters"].get("strong_test_demo_enabled", False)
    normalized = normalized.assign(
        booking_test_demo_name_flag=has_test_demo_name(raw, name_fields, pattern),
        # Keep strong signals as audit fields; the JSON switch controls exclusion.
        booking_test_demo_strong_signal_flag=has_configured_test_demo_signal(
            normalized, strong_signals
        ),
    ).assign(
        booking_test_demo_flag=lambda frame: (
            frame["booking_test_demo_name_flag"]
            | (
                frame["booking_test_demo_strong_signal_flag"]
                if strong_enabled
                else False
            )
        )
    )
    # The JSON rules define booking-time fallback and the strict honored source.
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
    """Apply the active test/demo rule while retaining all audit flags."""
    if enabled:
        filtered_referrals = referrals.loc[~referrals["referral_test_demo_flag"]]
        filtered_bookings = bookings.loc[~bookings["booking_test_demo_flag"]]
    else:
        filtered_referrals = referrals
        filtered_bookings = bookings

    def summary_row(
        table: pd.DataFrame,
        dataset: str,
        prefix: str,
        after_filter: int,
    ) -> dict[str, int | str]:
        name_flag = table[f"{prefix}_test_demo_name_flag"].fillna(False)
        strong_flag = table[f"{prefix}_test_demo_strong_signal_flag"].fillna(False)
        combined_flag = table[f"{prefix}_test_demo_flag"].fillna(False)
        return {
            "dataset": dataset,
            "before_filter": len(table),
            "name_pattern_only_flagged": int((name_flag & ~strong_flag).sum()),
            "strong_signal_only_flagged": int((strong_flag & ~name_flag).sum()),
            "flagged_by_both": int((name_flag & strong_flag).sum()),
            "excluded_by_active_filter": int(combined_flag.sum()) if enabled else 0,
            "after_filter": after_filter,
        }

    summary = pd.DataFrame(
        [
            summary_row(
                referrals,
                "Referral submissions",
                "referral",
                len(filtered_referrals),
            ),
            summary_row(bookings, "Bookings", "booking", len(filtered_bookings)),
        ]
    )
    return filtered_referrals, filtered_bookings, summary
