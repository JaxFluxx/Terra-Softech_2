# Referral Bypass Attribution Review

## Executive Summary

- **Primary result:** 4 booking-level records require manual referral-bypass review. All 4 are **Tier B** because each booking has multiple possible prior referrers; one also has a timeline ambiguity.
- **Honored rule:** both analysis routes use one definition: `booking_source = REFERRAL`.
- **Time-order correction:** the previous 28 same-enquiry source mismatches have booking dates earlier than referral submission. They are data-integrity records, not bypass evidence.
- **Stable result:** the 4 primary records remain under 30-, 60-, 90-, and 180-day attribution-window checks.
- **Reporting boundary:** agreement value is transaction context only. These extracts do not show commission eligibility, commission amount, or payout status.

## Decision Rules

| Rule | Applied definition |
|---|---|
| Primary unit | One completed booking |
| Primary identity | Exact `client + lead_id` |
| Time gate | `referral_submitted_on <= bookingDate`; use `booking_created_on` only if `bookingDate` is missing |
| Multiple referrals | Select the latest eligible prior referral; retain prior-referral and referrer counts for review |
| Honored | `booking_source = REFERRAL` |
| Test/demo filter | Exclude explicit test/demo words and names beginning with `test`, such as `TESTKYC` or `Testlead` |
| Project scope | A project change does not remove a record from review |

The honored rule checks recorded booking attribution. It does not prove that commission was paid.

## Booking-First Result

The primary route starts from each booking, finds an earlier referral for the same client and exact lead ID, then keeps the latest eligible referral.

| Metric | Before filter | After filter |
|---|---:|---:|
| Referral records | 5,448 | 4,585 |
| Booking records | 5,275 | 4,713 |
| Bookings with an eligible prior referral | 20 | 12 |
| Honored under the strict rule | 16 | 8 |
| Possible bypass records | 4 | 4 |

- The filter removes 863 referral rows and 562 booking rows with explicit test/demo name markers.
- It removes 8 honored matches and does not remove any of the 4 possible bypass records.
- The 4 records occur 1.4 to 3.5 days after the selected prior referral.
- Their prior-referrer counts are 10, 61, 134, and 236. Referral ownership is not unambiguous.
- **Tier A:** 0 records.
- **Tier B:** 4 records for manual attribution review.

The review list is in [`booking_priority_review_cases.csv`](../data/derived/booking_priority_review_cases.csv).

## Same-Enquiry Time Check

The referral extract contains 2,762 rows with a booking linked to the same enquiry.

| Time status | Booking source | Rows | Interpretation |
|---|---|---:|---|
| Reverse Time | `REFERRAL` | 2,718 | Booking date is earlier than referral submission |
| Reverse Time | `CHANNEL_PARTNER` | 28 | Source mismatch, but chronology is invalid |
| Time Valid | `REFERRAL` | 16 | Eligible chronology and honored |

The 28 `CHANNEL_PARTNER` rows are kept in [`reverse_time_data_integrity_cases.csv`](../data/derived/reverse_time_data_integrity_cases.csv). They are excluded from referral-bypass evidence.

## Sensitivity and Secondary Identity Review

- **Attribution windows:** the primary possible-bypass count remains 4 under 30, 60, 90, and 180 days.
- **Encrypted identity fallback:** exact encrypted mobile matching finds 3 additional possible records outside the exact lead-ID route. All remain **Tier C** until identity and lead ownership are confirmed.

Tier C records are listed in [`identity_match_review_cases.csv`](../data/derived/identity_match_review_cases.csv) and are not included in the primary count of 4.

## Review Files

1. Review the 4 Tier B bookings in [`booking_priority_review_cases.csv`](../data/derived/booking_priority_review_cases.csv).
2. Review the 28 reverse-time records in [`reverse_time_data_integrity_cases.csv`](../data/derived/reverse_time_data_integrity_cases.csv) as timestamp or extract-quality issues.
3. Confirm the 3 Tier C records in [`identity_match_review_cases.csv`](../data/derived/identity_match_review_cases.csv) before adding them to the primary list.

## Boundaries

- No official maximum attribution window was provided; tested windows are sensitivity checks only.
- The test/demo filter is a transparent name-based rule and may not capture every internal record.
- Exact encrypted mobile/email equality is secondary evidence and may contain shared-key or data-entry collisions.
- `agreementValue` cannot be converted into commission impact without commission eligibility, rate, reversal, and payout data.

## Supporting Files

- [`booking_centric_bypass_detection.ipynb`](../code/booking_centric_bypass_detection.ipynb)
- [`referral_bypass_summary.csv`](../data/derived/referral_bypass_summary.csv)
- [`filter_impact_summary.csv`](../data/derived/filter_impact_summary.csv)
- [`attribution_sensitivity_summary.csv`](../data/derived/attribution_sensitivity_summary.csv)
- [`same_enquiry_time_quality_summary.csv`](../data/derived/same_enquiry_time_quality_summary.csv)
