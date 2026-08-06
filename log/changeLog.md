# Referral Bypass Change Log

**Last updated:** 2026-08-06
**Package status:** Week 5 reusable analytics system completed and validated

## JSON Runtime Rule Binding

- Strengthened the JSON configuration from a documented rule contract into the
  runtime source for the main attribution decisions.
- The pipeline now reads the primary identity route, same-day time policy,
  latest-prior selection, honored source values, secondary identity routes,
  classification labels, and Ops priorities from
  `config/attribution_rules.json`.
- Kept raw-source-to-canonical-column mapping in `cleaning.py`; this is extract
  schema adaptation, not a business-attribution policy.
- Added tests showing that changing configured honored values or the same-day
  time rule changes runtime behavior on fictional records.
- Re-ran the accepted dataset after the refactor. The baseline remains:

  ```text
  eligible / honored / primary review = 12 / 8 / 4
  tier A / B / C = 0 / 4 / 3
  reverse-time source disagreements = 28
  primary booking IDs = 1206, 935, 3331, 4913
  ```

- This is an implementation improvement only. No accepted business rule, raw
  data, or headline result changed.

## Final Package Organization

- Aligned the active repository with the Week 5 manager-requested architecture:
  `README`, environment files, `config/`, `src/`, `tests/`, `code/`, `data/`,
  and `log/`.
- Kept only `code/5.1_lifecycle_and_decision.ipynb` as the current narrative
  notebook.
- Kept only the current metric dictionary, decision memo, and change log in the
  active `log/` directory.
- Moved historical notebooks, internal execution plans, superseded reports,
  run evidence, and local cache files to:

  ```text
  ../Terra Softech_2_append/
  ```

- The archive remains locally available for future reference but is outside the
  formal manager-facing package.
- No attribution rule, source data, derived output, headline result, or test
  expectation was changed during this organization step.

## Strict-Only JSON Configuration and Contract Hardening

- Replaced `config/attribution_rules.yaml` with
  `config/attribution_rules.json`, which is explicitly allowed by the Week 5
  assignment.
- Replaced the external YAML dependency with Python's built-in JSON loader and
  synchronized the CLI, tests, notebook, README, requirements, and metric
  dictionary.
- Retired Broad honored from active configuration, calculations, diagnostics,
  and reporting. Historical sensitivity checks found no incremental honored
  bookings:

  ```text
  30/60 days: strict 7 = broad 7
  90/180/unlimited: strict 8 = broad 8
  ```

- Kept `enquiry_source_norm` as review context and data-quality evidence; it no
  longer changes whether a booking is reported as honored.
- Preserved the required dual view as booking-centric attribution versus
  same-enquiry data integrity. This is separate from the retired Broad metric.
- Added an explicit primary-queue integrity validator that fails on duplicate
  booking rows, missing timeline fields, or reverse-time matches.
- Added standard Week 5 Ops Board columns, including `lead_id`, `lead_name`,
  `booking_timeline_at`, normalized source names, `referral_submitted_at`, and
  `same_project`.
- Added automated coverage for the time-gate fail-loud behavior, duplicate
  booking IDs, and the Ops Board minimum column contract.
- Standardized CSV float serialization to 12 significant digits so the CLI and
  notebook regenerate byte-consistent review files across local pandas
  environments.

## Week 5 Productization

### Deep-research hardening

- Added `AGENTS.md` with fixed rules, regression guardrails, commands, and the
  required change protocol.
- Added `pyproject.toml` for editable installation, the
  `referral-attribution` console command, and pytest `importlib` mode.
- Added optional local run tracking:
  - source-file inventory and hashes;
  - concise JSONL event log and command log;
  - pipeline checkpoint;
  - human-readable pipeline summary.
- Added CLI controls for custom config, run ID, tracked execution, and
  output-free validation.
- Kept tracking optional and Git-ignored to preserve the clean manager-facing
  package and avoid persisting review-level data.
- Did not add cloud CI/artifact upload, mandatory `uv`, numeric scoring, or
  Tableau automation because they are unnecessary or conflict with the current
  privacy/scope boundary.

### Configuration and reusable pipeline

- Moved the accepted identity, time, honored, filter, and confidence rules into
  `config/attribution_rules.json`.
- Extracted the accepted notebook logic into focused modules under
  `src/referral_attribution/`.
- Added one portable command that regenerates the full derived layer:

  ```bash
  PYTHONPATH=src python3 -m referral_attribution.pipeline
  ```

- Archived the older notebooks outside the active repository. The Week 5
  notebook reads pipeline outputs instead of duplicating matching logic.

### Lifecycle and diagnostics

- Added `lifecycle_funnel_summary.csv` with explicit grains and denominators.
- Added an identity-overlap bridge stage so the time-order drop is not confused
  with a conversion rate.
- Added same/cross-project, booking-source, multi-referrer, and
  30/60/90/180/unlimited window diagnostics.
- Kept Strict honored as the only active attribution metric; enquiry source
  remains review context rather than a second honored definition.

### Operational review queue

- Added `ops_review_board.csv` with 35 independently classified rows:
  - 28 `P0` reverse-time Data Integrity cases;
  - 4 `P1` primary Tier B attribution reviews;
  - 3 `P2` Tier C identity confirmations.
- Added operational actions, case reasons, relevant timestamps, identity
  method, and the honored definition used.
- Data Integrity and Tier C remain outside the primary count of four.

### Tests and documentation

- Added focused fictional-data rule tests and accepted-dataset regression tests.
- Added `log/metric_dictionary.md`, `log/decision_memo.md`, `README.md`, and
  `requirements.txt`. The internal `EXECPLAN.md` is retained in the local
  appendix archive rather than the manager-facing package.
- Preserved all accepted regression results:

  ```text
  eligible / strict honored / primary review = 12 / 8 / 4
  tier A / B / C = 0 / 4 / 3
  reverse-time source disagreements = 28
  primary booking IDs = 1206, 935, 3331, 4913
  ```

### Intentionally added derived files

- `filter_base_summary.csv`
- `lifecycle_funnel_summary.csv`
- `same_vs_cross_project_summary.csv`
- `attribution_window_sensitivity.csv`
- `booking_source_summary.csv`
- `multi_referrer_summary.csv`
- `ops_review_board.csv`

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
- Replaced the 29-column Tier B and 23-column Tier C exports with compact review tables containing only the decision-relevant fields and a record-level `review_reason`.
- Removed the redundant `initial_exploration_summary.csv` and `same_enquiry_time_valid_cases.csv` exports. Their results remain visible and validated inside the notebooks.
- Archive location:

  `../Terra_Softech_2_archive_20260725` (local archive outside this repository)

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

## Final Cleanup for GitHub Sync

- Removed four redundant derived files from the active package:
  `referral_bypass_summary.csv`, `tier_b_review_cases.csv`,
  `tier_c_review_cases.csv`, and `attribution_sensitivity_summary.csv`.
- `lifecycle_funnel_summary.csv` is now the single headline funnel output.
  `ops_review_board.csv` is the single operational queue and already contains
  Tier B, Tier C, and reverse-time Data Integrity records.
- Kept the separate filter and attribution-window tables because the Week 5
  assignment requires those audit and sensitivity views.
- Removed the corresponding legacy export code and regression-test references.
  The active package remains fully regenerated from one pipeline command.
