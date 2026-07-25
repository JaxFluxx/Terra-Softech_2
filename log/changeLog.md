# Referral Bypass Change Log

**Last updated:** 2026-07-25  
**Package status:** Clean package prepared for final review

## Manager Feedback Remediation

### 1. Time-Order Gate

- Applied `referral_submitted_on <= bookingDate`.
- Used `booking_created_on` only when `bookingDate` is missing.
- Reclassified 28 same-enquiry source mismatches as reverse-time data-integrity records.
- Confirmed 16 time-valid same-enquiry conversions; all 16 have `booking_source = REFERRAL`.

### 2. One Honored Definition

- Removed Broad as a formal reporting rule.
- Both analysis routes now use one definition:

  `Honored = booking_source == REFERRAL`

- The definition checks recorded attribution only. It does not prove commission payment.

### 3. Test / Demo Filter

- Added a transparent name-based filter for:
  - full markers: `test`, `demo`, `dummy`, `sample`, `training`, `internal`;
  - explicit `test` prefixes such as `TESTKYC`, `Testlead`, and `Testing`.
- Referral rows: `5,448 -> 4,585`.
- Booking rows: `5,275 -> 4,713`.
- Eligible prior-referral bookings: `20 -> 12`.
- Honored bookings: `16 -> 8`.
- Possible bypass records: `4 -> 4`.

### 4. Confidence Tiers

- **Tier A:** exact lead match, valid chronology, one clear prior referrer, and no timeline ambiguity.
- **Tier B:** exact lead match, but multiple referrers or timeline ambiguity requires manual review.
- **Tier C:** exact encrypted mobile/email match outside the primary lead-ID route; identity confirmation is required.
- **Data Integrity:** reverse-time or contradictory records; excluded from bypass evidence.

Current result:

- Tier A: `0`
- Tier B: `4`
- Tier C: `3 possible records`
- Reverse-time source disagreements: `28`

### 5. Clean Package

- Kept only active source data, reproducible notebooks, generated evidence, the formal report, and this change log.
- Moved checkpoints, personal walkthrough notes, AI memory notes, the previous change log, and the temporary rule-review notebook outside the project.
- Archive location:

  `/Users/jia/Desktop/工作/Terra Softech/Terra_Softech_2_archive_20260725`

## Latest Business Rules

| Rule | Current definition |
|---|---|
| Primary grain | One completed booking |
| Primary identity | Exact `client + lead_id` |
| Time gate | Referral submitted on or before `bookingDate`; fallback to `booking_created_on` only when needed |
| Multiple referrals | Select the latest eligible prior referral and retain all prior-referral/referrer counts |
| Honored | `booking_source = REFERRAL` |
| Test/demo control | Exclude explicit test/demo markers and clear `test`-prefix names |
| Project scope | A project change does not remove a record from review |
| Maximum attribution window | No assumed business limit; 30/60/90/180-day checks are sensitivity tests |
| Secondary identity | Exact encrypted mobile/email equality within the same client only; Tier C until identity is confirmed |
| Same-enquiry reverse time | Data-integrity issue, not bypass evidence |
| Agreement value | Transaction context only; not commission impact |

## Latest Results

| Result | Value |
|---|---:|
| Raw referral records | 5,448 |
| Raw booking records | 5,275 |
| Filtered referral records | 4,585 |
| Filtered booking records | 4,713 |
| Bookings with an eligible prior referral | 12 |
| Honored under the strict rule | 8 |
| Primary possible bypass records | 4 |
| Primary Tier A records | 0 |
| Primary Tier B records | 4 |
| Same-enquiry linked booking rows | 2,762 |
| Reverse-time same-enquiry rows | 2,746 |
| Reverse-time source disagreements | 28 |
| Time-valid same-enquiry rows | 16 |
| Time-valid same-enquiry unhonored rows | 0 |
| Tier C possible records | 3 |

The 4 primary records remain unchanged under 30-, 60-, 90-, and 180-day attribution-window checks. They are review candidates, not confirmed commission bypasses.

## Final Package Structure

```text
Terra Softech_2/
├── .gitattributes
├── code/
│   ├── initial_exploration.ipynb
│   └── booking_centric_bypass_detection.ipynb
├── data/
│   ├── raw/
│   │   ├── referral_submissions.csv
│   │   ├── booking_extracts.csv
│   │   └── dataset_guide.md
│   └── derived/
│       ├── initial_exploration_summary.csv
│       ├── data_quality_summary.csv
│       ├── filter_impact_summary.csv
│       ├── referral_bypass_summary.csv
│       ├── booking_priority_review_cases.csv
│       ├── same_enquiry_time_quality_summary.csv
│       ├── same_enquiry_time_valid_cases.csv
│       ├── reverse_time_data_integrity_cases.csv
│       ├── attribution_sensitivity_summary.csv
│       └── identity_match_review_cases.csv
└── log/
    ├── referralBypass_report.md
    └── changeLog.md
```

## Folder Purpose

- `code/`: runnable exploration and formal attribution-analysis notebooks.
- `data/raw/`: original extracts and the manager-provided data guide; read-only.
- `data/derived/`: notebook-generated summaries, review lists, sensitivity checks, and data-quality evidence.
- `log/`: formal manager-facing report and change history.

## Verification

- Both notebooks execute from the `code` folder using portable relative paths.
- The formal notebook contains no error outputs.
- Required derived files are regenerated from the formal notebook.
- The report, notebook, and CSV outputs use the same strict honored rule and the same latest counts.
