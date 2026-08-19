# Referral Bypass Change Log

**Last updated:** 2026-08-19
**Package status:** Week 5/6 assignment alignment audit completed and validated

## Week 5/6 Assignment Alignment Validation

- Ran the full test suite: `24 passed`.
- Regenerated all 16 derived CSV outputs through the documented pipeline
  command.
- Executed `code/6.1_impact_and_process.ipynb` from top to bottom with no
  error outputs.
- Confirmed the Week 6 deliverables: impact framing, Tier B value context,
  four-policy sensitivity, the 30-day warning specification, decision memo,
  metric dictionary, README guidance, and synthetic policy tests.
- The default JSON contract preserves the accepted `12 eligible / 8 strict
  honored / 4 primary review` baseline. The four review IDs remain `1206`,
  `935`, `3331`, and `4913`.
- Strong CRM-ID and unit-number signals are retained as visible data-quality
  flags. When explicitly enabled, they run as a separately tested sensitivity
  (`11 / 7 / 4`) and do not silently change the default primary funnel.

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

## Week 6: Impact Framing and Multi-Referrer Process Design

### Strong test/demo signal sensitivity

- Added JSON-configured strong test/demo signals: `booking_crm_id` values
  beginning with `DEMO-` and `unitNumber = TEST`.
- The default active filter retains the accepted `12 / 8 / 4` contract and
  excludes explicit name-pattern test/demo rows.
- Five additional booking rows match the configured strong signals. They are
  shown as data-quality flags by default and can be explicitly enabled as a
  tested sensitivity, which produces `11 / 7 / 4`.
- The primary review IDs remain `1206`, `935`, `3331`, and `4913`.
- `tests/test_pipeline_regression.py` confirms the default baseline and the
  explicitly enabled strong-signal sensitivity. This prevents silent drift in
  either view.

### Impact and value context

- Added `impact_framing_summary.csv` with separate workload and conditional
  quality denominators.
- Added `tier_b_agreement_context.csv`; it flags repeated-digit and invalid
  values without removing the attribution case or treating agreement value as
  commission.
- Added Tier B agreement-value sum, median, minimum, and maximum to the
  impact framing table. These remain transaction context only.

### Multi-referrer policy and product process

- Added configurable policy scenarios P-LAST, P-FIRST, P-MANUAL, and
  P-SAME-PROJECT-LAST.
- Selected P-MANUAL as the 90-day provisional policy: a single prior referrer
  may receive an owner candidate; two or more distinct prior referrers require
  manual review.
- Added the following reproducible outputs:
  `multi_referrer_policy_sensitivity.csv`,
  `multi_referrer_policy_case_matrix.csv`, and
  `process_window_and_policy_sensitivity.csv`.
- Added the baseline Tier B booking IDs for each tested process window and a
  separate window-recomputed Tier B view. This distinguishes cases that would
  trigger a warning from cases that still need a multi-referrer escalation.
- Added a 30-day non-referral booking warning rule, decision table, and event
  field contract. It is a soft-warning pilot; it does not automatically assign
  payout or resolve cross-project ownership.

### Validation and documentation

- Added `tests/test_process_rules.py` for strong test signals, value sanity,
  warning outcomes, and ownership policy behavior.
- Added `log/multi_referrer_policy_brief.md` and
  `log/process_rule_spec.md`; refreshed `log/decision_memo.md`, the metric
  dictionary, README, and Week 6 notebook.
- Preserved the Week 5 booking-first route, latest-prior selection, strict
  honored definition, Tier honesty, reverse-time separation, and agreement
  value boundary.
