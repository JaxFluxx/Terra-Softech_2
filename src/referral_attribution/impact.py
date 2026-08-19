"""Manager-safe impact framing for the accepted referral workflow."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .quality import evaluate_value_sanity


def _safe_rate(numerator: int, denominator: int) -> float:
    """Return a rate only when its denominator is available."""
    return numerator / denominator if denominator else float("nan")


def _identity_overlap_booking_count(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    identity_rule: dict[str, Any],
) -> int:
    """Count filtered bookings sharing the configured primary identity key."""
    booking_fields = identity_rule["booking_fields"]
    referral_fields = identity_rule["referral_fields"]
    booking_keys = bookings.loc[
        bookings["booking_lead_id"].notna(),
        [*booking_fields, "booking_id"],
    ]
    referral_keys = referrals.loc[
        referrals["referral_lead_id"].notna(),
        referral_fields,
    ].drop_duplicates()
    return int(
        booking_keys.merge(
            referral_keys,
            left_on=booking_fields,
            right_on=referral_fields,
            how="inner",
            validate="many_to_one",
        )["booking_id"].nunique()
    )


def _tier_b_cases(primary_review: pd.DataFrame) -> pd.DataFrame:
    """Keep only ambiguous primary cases for agreement context."""
    return primary_review.loc[
        primary_review["confidence_tier"].astype("string").str.startswith(
            "Tier B", na=False
        )
    ]


def build_tier_b_agreement_context(
    primary_review: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Export one row per Tier B case without presenting value as commission."""
    tier_b = _tier_b_cases(primary_review).assign(
        value_sanity_flag=lambda frame: evaluate_value_sanity(
            frame["agreement_value"], rules=rules
        ),
        agreement_value_context=(
            "Transaction context only; not commission, loss, or recoverable impact."
        ),
    )
    columns = [
        "booking_id",
        "booking_timeline_at",
        "booking_source_norm",
        "booking_lead_id",
        "referral_enquiry_id",
        "referral_submitted_at",
        "referrer_user_id",
        "referrer_name",
        "prior_referral_count",
        "prior_referrer_count",
        "days_between_referral_and_booking",
        "same_project",
        "timeline_ambiguity_flag",
        "agreement_value",
        "value_sanity_flag",
        "review_reason",
        "agreement_value_context",
    ]
    return tier_b.loc[:, columns].rename(columns={"booking_lead_id": "lead_id"})


def build_impact_framing_summary(
    referrals: pd.DataFrame,
    bookings: pd.DataFrame,
    primary_matches: pd.DataFrame,
    primary_review: pd.DataFrame,
    tier_c_review: pd.DataFrame,
    reverse_time: pd.DataFrame,
    rules: dict[str, Any],
) -> pd.DataFrame:
    """Build explicit denominators and honest context for leadership review."""
    identity_overlap = _identity_overlap_booking_count(
        referrals,
        bookings,
        rules["identity"]["primary_route"],
    )
    eligible = int(primary_matches["booking_id"].nunique())
    strict_honored = int(
        primary_matches.loc[primary_matches["honored_strict"], "booking_id"].nunique()
    )
    review_count = int(primary_review["booking_id"].nunique())
    tier_b = _tier_b_cases(primary_review)
    tier_b_count = int(tier_b["booking_id"].nunique())
    tier_c_count = int(tier_c_review["booking_id"].nunique())
    reverse_time_count = int(len(reverse_time))
    value_flags = evaluate_value_sanity(tier_b["agreement_value"], rules=rules)
    agreement_values = pd.to_numeric(
        tier_b["agreement_value"], errors="coerce"
    ).dropna()

    def agreement_stat(statistic: str) -> float:
        """Return one descriptive value-context statistic when available."""
        if agreement_values.empty:
            return 0.0
        return float(getattr(agreement_values, statistic)())

    def metric(
        metric_key: str,
        label: str,
        value: int | float,
        numerator: int | None,
        denominator: int | None,
        unit: str,
        definition: str,
        decision_use: str,
        not_a_claim: str,
    ) -> dict[str, Any]:
        return {
            "metric_key": metric_key,
            "metric": label,
            "value": value,
            "numerator": numerator,
            "denominator": denominator,
            "unit": unit,
            "definition": definition,
            "decision_use": decision_use,
            "not_a_claim": not_a_claim,
        }

    rows = [
        metric(
            "filtered_bookings",
            "Filtered production-like bookings",
            len(bookings),
            None,
            None,
            "bookings",
            "Bookings remaining after the configured test/demo filter.",
            "Base for operational workload context.",
            "Not a count of referral-attributable bookings.",
        ),
        metric(
            "identity_overlap_bookings",
            "Identity-overlap bookings",
            identity_overlap,
            identity_overlap,
            len(bookings),
            "bookings",
            "Filtered bookings sharing exact client + lead_id with at least one referral.",
            "Shows where the time-order gate has evidence to evaluate.",
            "Not a conversion or bypass rate.",
        ),
        metric(
            "eligible_prior_referral_bookings",
            "Eligible prior-referral bookings",
            eligible,
            eligible,
            identity_overlap,
            "bookings",
            "Bookings with at least one time-valid referral under the primary route.",
            "Conditional cohort for strict honored and primary review rates.",
            "Not the total booking population.",
        ),
        metric(
            "strict_honored_rate",
            "Strict honored rate among eligible bookings",
            _safe_rate(strict_honored, eligible),
            strict_honored,
            eligible,
            "rate",
            "Eligible bookings whose recorded booking source is REFERRAL.",
            "Checks recorded attribution inside the eligible path.",
            "Does not prove commission payment or ownership.",
        ),
        metric(
            "primary_review_rate",
            "Primary review rate among eligible bookings",
            _safe_rate(review_count, eligible),
            review_count,
            eligible,
            "rate",
            "Eligible bookings that are not strictly honored.",
            "Conditional attribution-quality diagnostic.",
            "Not a system-wide bypass rate.",
        ),
        metric(
            "primary_review_per_1000_filtered_bookings",
            "Primary review cases per 1,000 filtered bookings",
            _safe_rate(review_count * 1000, len(bookings)),
            review_count,
            len(bookings),
            "cases per 1,000 bookings",
            "Primary review cases scaled to the filtered production-like booking base.",
            "Headline estimate of routine Ops review workload.",
            "Not a commission-loss or fraud rate.",
        ),
        metric(
            "tier_b_primary_cases",
            "Tier B primary review cases",
            tier_b_count,
            tier_b_count,
            review_count,
            "cases",
            "Primary review bookings with multiple prior referrers or timeline ambiguity.",
            "Shows ownership ambiguity that requires manual review.",
            "Not confirmed bypass or fraud.",
        ),
        metric(
            "tier_c_identity_cases",
            "Tier C identity cases",
            tier_c_count,
            None,
            None,
            "cases",
            "Secondary exact encrypted-identity matches outside the primary route.",
            "Separate identity-confirmation queue.",
            "Does not change the primary review count.",
        ),
        metric(
            "reverse_time_source_disagreements",
            "Reverse-time source disagreements",
            reverse_time_count,
            None,
            None,
            "records",
            "Same-enquiry records where booking time precedes referral time and sources disagree.",
            "Data Integrity backlog for chronology repair.",
            "Never primary bypass evidence or unpaid commission count.",
        ),
        metric(
            "tier_b_agreement_value_sum",
            "Tier B agreement value sum",
            agreement_stat("sum"),
            None,
            None,
            "agreement-value context",
            "Sum of recorded agreement values for Tier B cases, retained with quality flags.",
            "Prioritization context for source-CRM review.",
            "Not commission, loss, margin, or recoverable impact.",
        ),
        metric(
            "tier_b_agreement_value_median",
            "Tier B agreement value median",
            agreement_stat("median"),
            None,
            None,
            "agreement-value context",
            "Median of recorded Tier B agreement values, including values that retain a separate sanity flag.",
            "Reduces the influence of one very large recorded value during case review.",
            "Not commission, loss, margin, or recoverable impact.",
        ),
        metric(
            "tier_b_agreement_value_min",
            "Tier B agreement value minimum",
            agreement_stat("min"),
            None,
            None,
            "agreement-value context",
            "Smallest recorded Tier B agreement value, retained with quality flags.",
            "Provides the lower bound of the review-queue transaction context.",
            "Not commission, loss, margin, or recoverable impact.",
        ),
        metric(
            "tier_b_agreement_value_max",
            "Tier B agreement value maximum",
            agreement_stat("max"),
            None,
            None,
            "agreement-value context",
            "Largest recorded Tier B agreement value, retained with quality flags.",
            "Highlights records that need source-value verification before prioritization.",
            "Not commission, loss, margin, or recoverable impact.",
        ),
        metric(
            "tier_b_repeated_digit_flags",
            "Tier B repeated-digit value flags",
            int(value_flags.eq("Repeated-digit pattern").sum()),
            None,
            None,
            "cases",
            "Tier B cases whose agreement value looks like a keyboard-pattern placeholder.",
            "Prompts value verification without removing the case.",
            "Does not invalidate the attribution review by itself.",
        ),
        metric(
            "tier_b_missing_value_flags",
            "Tier B missing agreement value flags",
            int(value_flags.eq("Not available").sum()),
            None,
            None,
            "cases",
            "Tier B cases without a usable recorded agreement value.",
            "Shows whether source-value verification is required before value context can be reviewed.",
            "Does not invalidate the attribution review by itself.",
        ),
        metric(
            "tier_b_non_positive_value_flags",
            "Tier B non-positive agreement value flags",
            int(value_flags.eq("Non-positive value").sum()),
            None,
            None,
            "cases",
            "Tier B cases with a zero or negative recorded agreement value.",
            "Prompts source-value verification without suppressing the attribution case.",
            "Does not invalidate the attribution review by itself.",
        ),
    ]
    return pd.DataFrame(rows)
