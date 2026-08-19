"""Single-entry referral attribution analytics pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from .classification import (
    build_ops_review_board,
    classify_primary_matches,
    classify_secondary_matches,
)
from .cleaning import filter_test_demo, normalize_bookings, normalize_referrals
from .config import find_project_root, load_rules
from .funnel import (
    build_lifecycle_funnel,
    build_multi_referrer_diagnostic,
    build_project_diagnostic,
    build_source_diagnostic,
    build_window_sensitivity,
)
from .io import load_source_tables, write_csv
from .impact import build_impact_framing_summary, build_tier_b_agreement_context
from .matching import (
    analyze_same_enquiry,
    build_secondary_identity_matches,
    build_time_valid_pairs,
    combine_secondary_routes,
    select_latest_prior_referral,
)
from .quality import (
    build_data_quality_summary,
    validate_primary_queue_integrity,
    validate_regression,
)
from .process_rules import (
    build_multi_referrer_policy_case_matrix,
    build_multi_referrer_policy_sensitivity,
    build_process_window_and_policy_sensitivity,
)
from .run_tracking import RunTracker, default_run_id, utc_now


SAME_ENQUIRY_EXPORT_COLUMNS = [
    "review_class",
    "client_name",
    "referral_enquiry_id",
    "referral_submitted_at",
    "referral_source_norm",
    "referral_lead_id",
    "lead_name",
    "referrer_user_id",
    "referrer_name",
    "referral_project_id",
    "projectName",
    "booking_on_referral_id",
    "booking_on_referral_at",
    "booking_on_referral_source_norm",
    "same_enquiry_time_status",
    "same_enquiry_honored_strict",
    "source_disagreement_flag",
    "referral_test_demo_flag",
]


def _build_filter_impact(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    filtered_referrals: pd.DataFrame,
    filtered_bookings: pd.DataFrame,
    unfiltered_matches: pd.DataFrame,
    primary_matches: pd.DataFrame,
) -> pd.DataFrame:
    rows = [
        ("Referral rows", len(referrals), len(filtered_referrals)),
        ("Booking rows", len(bookings), len(filtered_bookings)),
        (
            "Bookings with eligible prior referral",
            unfiltered_matches["booking_id"].nunique(),
            primary_matches["booking_id"].nunique(),
        ),
        (
            "Honored under strict rule",
            unfiltered_matches.loc[
                unfiltered_matches["honored_strict"], "booking_id"
            ].nunique(),
            primary_matches.loc[
                primary_matches["honored_strict"], "booking_id"
            ].nunique(),
        ),
        (
            "Possible bypass records",
            unfiltered_matches.loc[
                ~unfiltered_matches["honored_strict"], "booking_id"
            ].nunique(),
            primary_matches.loc[
                ~primary_matches["honored_strict"], "booking_id"
            ].nunique(),
        ),
    ]
    return pd.DataFrame(
        rows,
        columns=["metric", "before_filter", "after_filter"],
    ).assign(removed=lambda frame: frame["before_filter"] - frame["after_filter"])


def run_pipeline(
    project_root: Path | None = None,
    config_path: Path | None = None,
    write_outputs: bool = True,
    verbose: bool = True,
    run_id: str | None = None,
    track_run: bool = False,
) -> dict[str, Any]:
    """Run the complete accepted attribution workflow."""
    root = (project_root or find_project_root()).resolve()
    rules = load_rules(root, config_path=config_path)
    raw_dir = root / "data" / "raw"
    output_dir = root / rules["outputs"]["directory"]
    started_at = utc_now()
    tracker = RunTracker(root, run_id) if track_run else None

    if tracker:
        tracker.write_plan()
        tracker.write_command(
            "python3 -m referral_attribution.pipeline "
            f"--track-run --run-id {tracker.run_id}"
        )
        tracker.log_event(
            stage="pipeline",
            action="start",
            status="ok",
            note="Started accepted referral attribution workflow.",
        )

    referrals_raw, bookings_raw, source_files = load_source_tables(raw_dir)
    if tracker:
        tracker.write_inventory(
            [
                raw_dir / source_files["referral_file"],
                raw_dir / source_files["booking_file"],
            ]
        )
        tracker.log_event(
            stage="input",
            action="load_and_validate",
            status="ok",
            note="Loaded two source extracts and validated required columns.",
        )
    referrals = normalize_referrals(referrals_raw, rules)
    bookings = normalize_bookings(bookings_raw, rules)
    data_quality = build_data_quality_summary(referrals, bookings, rules=rules)

    filtered_referrals, filtered_bookings, filter_base = filter_test_demo(
        referrals,
        bookings,
        enabled=rules["filters"]["test_demo_enabled"],
    )

    # Keep same-enquiry integrity checks on the full normalized referral extract.
    # Primary matching continues to use the filtered production-like slice.
    # JSON is the runtime source for matching, time, honored, and identity rules.
    strict_sources = rules["honored"]["strict"]["accepted_values"]
    identity_rule = rules["identity"]["primary_route"]
    allow_same_day = rules["time"]["allow_referral_on_booking_date"]
    latest_prior = rules["time"]["latest_prior_referral"]
    same_enquiry, same_enquiry_summary, reverse_time, same_enquiry_valid = (
        analyze_same_enquiry(referrals, accepted_sources=strict_sources)
    )

    unfiltered_pairs = build_time_valid_pairs(
        referrals,
        bookings,
        identity_rule=identity_rule,
        allow_referral_on_booking_date=allow_same_day,
    )
    filtered_pairs = build_time_valid_pairs(
        filtered_referrals,
        filtered_bookings,
        identity_rule=identity_rule,
        allow_referral_on_booking_date=allow_same_day,
    )
    unfiltered_matches = select_latest_prior_referral(
        unfiltered_pairs,
        latest_prior_referral=latest_prior,
    )
    selected_primary = select_latest_prior_referral(
        filtered_pairs,
        max_window_days=rules["time"]["primary_window_days"],
        latest_prior_referral=latest_prior,
    )
    validate_primary_queue_integrity(selected_primary)
    primary_matches, primary_review = classify_primary_matches(
        selected_primary,
        rules=rules,
    )

    lead_route_ids = set(primary_matches["booking_id"].dropna().astype("string"))
    secondary_routes = [
        build_secondary_identity_matches(
            filtered_referrals,
            filtered_bookings,
            route["referral_key"],
            route["booking_key"],
            route["name"],
            lead_route_ids,
            allow_referral_on_booking_date=allow_same_day,
        )
        for route in rules["identity"]["secondary_routes"]
    ]
    tier_c_review = classify_secondary_matches(
        combine_secondary_routes(*secondary_routes),
        rules=rules,
    )

    regression = validate_regression(
        primary_matches,
        primary_review,
        tier_c_review,
        reverse_time,
        same_enquiry_valid,
        rules=rules,
    )

    filter_impact = _build_filter_impact(
        referrals,
        bookings,
        filtered_referrals,
        filtered_bookings,
        unfiltered_matches,
        primary_matches,
    )
    old_sensitivity = pd.concat(
        [
            build_window_sensitivity(
                unfiltered_pairs,
                rules["time"]["attribution_windows_days"],
                cohort="Before test/demo filter",
                latest_prior_referral=latest_prior,
            ),
            build_window_sensitivity(
                filtered_pairs,
                rules["time"]["attribution_windows_days"],
                cohort="After test/demo filter",
                latest_prior_referral=latest_prior,
            ),
        ],
        ignore_index=True,
    )
    window_sensitivity = old_sensitivity.loc[
        old_sensitivity["cohort"].eq("After test/demo filter")
    ].reset_index(drop=True)

    lifecycle_funnel = build_lifecycle_funnel(
        filtered_referrals,
        filtered_bookings,
        primary_matches,
        reverse_time_count=len(reverse_time),
        identity_rule=identity_rule,
        honored_label=rules["honored"]["strict"]["label"],
    )
    project_diagnostic = build_project_diagnostic(primary_matches)
    source_diagnostic = build_source_diagnostic(
        filtered_bookings,
        primary_matches,
    )
    multi_referrer = build_multi_referrer_diagnostic(primary_matches)
    impact_framing = build_impact_framing_summary(
        filtered_referrals,
        filtered_bookings,
        primary_matches,
        primary_review,
        tier_c_review,
        reverse_time,
        rules,
    )
    tier_b_agreement_context = build_tier_b_agreement_context(primary_review, rules)
    multi_referrer_policy = build_multi_referrer_policy_sensitivity(
        filtered_pairs,
        rules,
    )
    multi_referrer_policy_case_matrix = build_multi_referrer_policy_case_matrix(
        filtered_pairs,
        rules,
    )
    process_window_and_policy = build_process_window_and_policy_sensitivity(
        filtered_pairs,
        rules,
    )
    ops_board = build_ops_review_board(
        primary_review,
        tier_c_review,
        reverse_time,
        rules=rules,
    )
    reverse_export = reverse_time[
        ["issue_reason", *SAME_ENQUIRY_EXPORT_COLUMNS]
    ]
    tables = {
        "data_quality_summary.csv": data_quality,
        "filter_base_summary.csv": filter_base,
        "filter_impact_summary.csv": filter_impact,
        "same_enquiry_time_quality_summary.csv": same_enquiry_summary,
        "reverse_time_data_integrity_cases.csv": reverse_export,
        "lifecycle_funnel_summary.csv": lifecycle_funnel,
        "same_vs_cross_project_summary.csv": project_diagnostic,
        "attribution_window_sensitivity.csv": window_sensitivity,
        "booking_source_summary.csv": source_diagnostic,
        "multi_referrer_summary.csv": multi_referrer,
        "impact_framing_summary.csv": impact_framing,
        "tier_b_agreement_context.csv": tier_b_agreement_context,
        "multi_referrer_policy_sensitivity.csv": multi_referrer_policy,
        "multi_referrer_policy_case_matrix.csv": multi_referrer_policy_case_matrix,
        "process_window_and_policy_sensitivity.csv": process_window_and_policy,
        "ops_review_board.csv": ops_board,
    }

    if write_outputs:
        for filename, table in tables.items():
            write_csv(table, output_dir / filename)

    if tracker:
        output_files = list(tables) if write_outputs else []
        tracker.write_checkpoint(
            stage="pipeline",
            started_at=started_at,
            regression=regression,
            output_files=output_files,
        )
        tracker.write_summary(regression)
        tracker.log_event(
            stage="pipeline",
            action="complete",
            status="ok",
            note=(
                f"Regression passed; {len(output_files)} derived files "
                "created or refreshed."
            ),
        )

    if verbose:
        print(f"Project root: {root}")
        print(
            f"Sources: {source_files['referral_file']} ({len(referrals):,}), "
            f"{source_files['booking_file']} ({len(bookings):,})"
        )
        print(
            "Accepted results: "
            f"{regression['eligible_bookings']} eligible, "
            f"{regression['strict_honored']} strict honored, "
            f"{regression['primary_review']} primary review, "
            f"{regression['tier_c']} Tier C, "
            f"{regression['reverse_time_source_disagreement']} reverse-time."
        )
        if write_outputs:
            print(f"Wrote {len(tables)} derived files to {output_dir}")

    return {
        "project_root": root,
        "rules": rules,
        "source_files": source_files,
        "referrals": referrals,
        "bookings": bookings,
        "filtered_referrals": filtered_referrals,
        "filtered_bookings": filtered_bookings,
        "filtered_pairs": filtered_pairs,
        "primary_matches": primary_matches,
        "primary_review": primary_review,
        "tier_c_review": tier_c_review,
        "reverse_time": reverse_time,
        "same_enquiry_time_valid": same_enquiry_valid,
        "regression": regression,
        "tables": tables,
        "run_id": tracker.run_id if tracker else None,
        "run_root": tracker.run_root if tracker else None,
    }


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Run the referral attribution analytics pipeline."
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Optional repository root. By default it is discovered from cwd.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Optional JSON rule file. Relative paths resolve from project root.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional filesystem-safe identifier for local run evidence.",
    )
    parser.add_argument(
        "--track-run",
        action="store_true",
        help="Write local inventory, logs, checkpoint, and summary under runs/.",
    )
    parser.add_argument(
        "--write-outputs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write derived CSV outputs (default: enabled).",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output.",
    )
    args = parser.parse_args()
    track_run = args.track_run or args.run_id is not None
    run_id = args.run_id or (default_run_id() if track_run else None)

    try:
        run_pipeline(
            project_root=args.project_root,
            config_path=args.config,
            write_outputs=args.write_outputs,
            verbose=not args.quiet,
            run_id=run_id,
            track_run=track_run,
        )
    except Exception as error:
        if track_run and run_id:
            try:
                root = (args.project_root or find_project_root()).resolve()
                RunTracker(root, run_id).write_failure("pipeline", error)
            except Exception:
                pass
        raise


if __name__ == "__main__":
    main()
