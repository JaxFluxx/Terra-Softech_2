"""Input discovery, loading, schema validation, and output writing."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_REFERRAL_COLUMNS = {
    "Client name",
    "referral_enquiry_id",
    "referral_submitted_on",
    "source",
    "project_id",
    "referrer_user_id",
    "referrer_name",
    "lead_id",
    "lead_name",
    "mobileNumber",
    "email",
    "booking_on_referral_enquiry_id",
    "booking_on_referral_date",
    "booking_on_referral_source",
}

REQUIRED_BOOKING_COLUMNS = {
    "Client name",
    "booking_id",
    "bookingDate",
    "booking_created_on",
    "booking_source",
    "agreementValue",
    "enquiry_id",
    "enquiry_source",
    "lead_id",
    "project_id",
    "lead_name",
    "mobileNumber",
    "email",
}


def validate_required_columns(
    table: pd.DataFrame,
    required_columns: set[str],
    table_name: str,
) -> None:
    """Fail loudly when a source extract cannot support the accepted rules."""
    missing = sorted(required_columns - set(table.columns))
    if missing:
        raise ValueError(
            f"{table_name} is missing required columns: {missing}. "
            "Check the extract schema before running attribution."
        )


def load_source_tables(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Read source CSVs as strings and identify each table by its schema."""
    csv_files = sorted(raw_dir.glob("*.csv"))
    if len(csv_files) < 2:
        raise FileNotFoundError(
            f"Expected referral and booking CSV files in {raw_dir}; found {len(csv_files)}."
        )

    loaded = {
        path.name: pd.read_csv(path, dtype="string", low_memory=False)
        for path in csv_files
    }
    referral_file = next(
        (
            name
            for name, table in loaded.items()
            if {"referral_enquiry_id", "referrer_user_id"}.issubset(table.columns)
        ),
        None,
    )
    booking_file = next(
        (
            name
            for name, table in loaded.items()
            if {"booking_id", "bookingDate", "booking_source"}.issubset(table.columns)
        ),
        None,
    )

    if referral_file is None or booking_file is None:
        raise ValueError(
            "Could not identify both extracts from their columns. "
            f"Files inspected: {sorted(loaded)}"
        )

    referrals = loaded[referral_file]
    bookings = loaded[booking_file]
    validate_required_columns(referrals, REQUIRED_REFERRAL_COLUMNS, "Referral extract")
    validate_required_columns(bookings, REQUIRED_BOOKING_COLUMNS, "Booking extract")

    return referrals, bookings, {
        "referral_file": referral_file,
        "booking_file": booking_file,
    }


def write_csv(table: pd.DataFrame, path: Path) -> None:
    """Write a deterministic CSV while preserving string IDs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # 固定浮点写出精度
    # -> 避免不同 pandas 版本产生无业务意义的末位差异
    table.to_csv(path, index=False, float_format="%.12g")
