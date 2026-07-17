# Terra Softech_2 Referral Bypass Project Log

> Shared memory for future AI / reviewer handoff.  
> Please update this file whenever code, notebook logic, output files, or decision rules change.

## Project Goal

The current project checks whether a customer submitted a referral and whether the later booking was honored as a referral.

In plain language:

- A referrer submits a referral for a lead.
- The referred lead may later make a booking.
- If the booking is marked as `REFERRAL`, the referral is considered honored.
- If the lead had a prior referral but the later booking is marked as `CHANNEL_PARTNER`, `DIRECT`, null, or another non-referral source, it may be a referral bypass candidate.

The manager described the business concern as:

> I referred you. When you purchased something, I should get commission. But instead of showing my referral purchased something, the company may show it as an independent booking to save commission.

## Source Data

Source folder:

`/Users/jia/Desktop/工作/Terra Softech/Terra Softech_2/referral-bypass-dataset-guide`

Files:

- `referral-bypass-dataset-guide.md`
- `CustomQueryReport_15_07_2026_06_11_31.csv`
  - Referral submissions table.
  - One row = one referral enquiry / referral submission.
- `CustomQueryReport_15_07_2026_06_12_51.csv`
  - Bookings table.
  - One row = one booking.

## Important Business Terms

- `Referrer`: the person who submitted the referral.
- `Lead`: the referred customer / prospective buyer.
- `Referral enquiry`: an enquiry whose source is `REFERRAL`.
- `Booking`: the final purchase / booking record.
- `Honored referral`: a booking where `booking_source` or `enquiry_source` is marked as `REFERRAL`.
- `Referral bypass`: a suspected case where the lead had a referral before booking, but the booking was not marked as `REFERRAL`.

## Current Analysis Direction

Chosen direction: booking-centric bypass detection.

Main logic:

1. Start from each booking.
2. Find whether the same `lead_id` had any referral before the booking date.
3. If multiple prior referrals exist, use the latest referral before the booking.
4. Check whether the booking is marked as `REFERRAL`.
5. If not marked as `REFERRAL`, export it as a suspected bypass case.

Current matching rule:

```text
same lead_id
referral_submitted_on <= bookingDate
match latest prior referral before booking
```

Why only 20 matched cases from 5,000+ rows:

- The raw tables contain all referral records and all bookings.
- A case is only analyzable for bypass if the same lead has a referral before the booking.
- Many referrals did not later convert.
- Many bookings have no matching prior referral.
- Some referrals happened after the booking and cannot explain that booking.
- The current version uses conservative exact `lead_id` matching, not fuzzy matching.

## Current Notebook

Formal analysis notebook:

`/Users/jia/Desktop/工作/Terra Softech/Terra Softech_2/Referral_Bypass_Analysis/2_Booking_Centric_Bypass_Detection.ipynb`

Exploration notebook:

`/Users/jia/Desktop/工作/Terra Softech/Terra Softech_2/Exploration/referral_bypass_initial_exploration.ipynb`

The formal notebook has been executed successfully top-to-bottom with no notebook error outputs.

## Current Key Results

Raw dataset size:

- Referral records: `5,448`
- Booking records: `5,275`
- Unique referral leads: `1,000`
- Unique booking leads: `701`

Core matching result:

- Bookings with at least one prior referral: `20`
- Honored referral bookings among those: `16`
- Suspected referral bypass bookings: `4`
- Suspected bypass leads: `4`
- Suspected bypass total agreement value: `18,161,111`

Same-enquiry attribution check:

- Own referral enquiry honored: `2,734`
- Own referral enquiry not honored: `28`
- Leads involved in same-enquiry anomaly: `7`

Overlap check between the two diagnostic views:

- Overlapping leads between `4` suspected booking-level bypass cases and `28` same-enquiry anomalies: `1`
- Overlapping referral enquiry IDs: `0`
- Strict booking / enquiry ID overlaps: `0`
- Combined unique leads across both diagnostic views after lead-level deduplication: `10`

Current reporting position:

- Report the `4` suspected bypass cases and the `28` same-enquiry attribution anomalies as two separate diagnostic views.
- They partially overlap at the lead level only, specifically lead `887`.
- They should not be described as the exact same records because there is no referral enquiry ID or strict booking/enquiry ID overlap.
- They also should not be casually added as `32` independent customer-level issues because one lead appears in both views.

## Current Output Files

Output folder:

`/Users/jia/Desktop/工作/Terra Softech/Terra Softech_2/Referral_Bypass_Analysis/outputs`

Important outputs:

- `referral_bypass_summary.csv`
  - Overall counts and key metrics.
- `suspected_bypass_cases.csv`
  - The 4 most important suspected bypass cases.
- `booking_referral_match_cases.csv`
  - All 20 booking-prior-referral matched cases.
- `same_enquiry_attribution_anomalies.csv`
  - 28 same-referral-enquiry attribution anomalies.
- `tableau_referral_bypass_review_export.csv`
  - Compact review table for Tableau or manager review.
- `summary_by_case_type.csv`
  - Honored vs suspected bypass summary.
- `suspected_bypass_by_project.csv`
  - Suspected bypass summary by project.
- `suspected_bypass_by_source.csv`
  - Suspected bypass summary by booking/enquiry source.
- `manual_review_summary.csv`
  - Whether cases need manual review due to multiple prior referrals/referrers/projects.
- `overlap_summary.csv`
  - Summary of overlap between booking-level bypass cases and same-enquiry anomalies.
- `overlap_by_lead.csv`
  - Lead-level overlap table.
- `overlap_by_referral_enquiry_id.csv`
  - Referral enquiry ID-level overlap table.
- `overlap_by_booking_or_enquiry_id.csv`
  - Strict booking / enquiry ID overlap table.

## Data Cleaning / Logic Notes

- IDs are kept as strings to avoid unsafe float -> int -> string conversion.
- Date fields are parsed with mixed-format handling.
- String `"NULL"` and blank source values are normalized to `<NULL>`.
- Null `booking_source` / `enquiry_source` is treated as not referral, following the guide.
- A booking is treated as honored if either `booking_source` or `enquiry_source` equals `REFERRAL`.
- `lead_id` is the primary identity matching key.
- Encrypted mobile/email exact matching is not yet added.
- No fuzzy matching is used.
- No max attribution window is set yet.

## Known Issues / Next Questions

Questions to confirm with manager later:

- Should there be a maximum attribution window, such as 30, 60, or 90 days?
- Should encrypted mobile/email exact matching be added for bookings with missing `lead_id`?
- Should commission value be estimated from `agreementValue`, or is there a separate commission table?
- For multi-referral cases, is latest prior referral always the correct business rule?
- Should each booking be matched only to the latest prior referral, or should any historical prior referral qualify?
- For same-enquiry anomalies, should these be treated as suspected bypass cases, attribution quality issues, or a separate review category?
- If booking-level bypass and same-enquiry anomalies overlap only at the lead level, how should they be reported?

## Change History

### 2026-07-17

- Created this project log for AI handoff and future code-change tracking.
- Current formal notebook already exists and has been executed successfully.
- Current confirmed result:
  - 20 bookings have at least one prior referral.
  - 16 are honored as referral.
  - 4 are suspected bypass candidates.
  - 28 same-enquiry attribution anomalies were found.

### 2026-07-17 - Overlap Check Update

- Added notebook section: `Overlap Check: Booking-Level Bypass vs Same-Enquiry Attribution Anomalies`.
- Added notebook explanation section: `How to Interpret the Two Findings`.
- Added manager-facing questions section.
- Generated new overlap outputs:
  - `overlap_summary.csv`
  - `overlap_by_lead.csv`
  - `overlap_by_referral_enquiry_id.csv`
  - `overlap_by_booking_or_enquiry_id.csv`
- Key overlap result:
  - `4` suspected booking-level bypass cases and `28` same-enquiry anomalies overlap at lead level only.
  - Overlapping lead count: `1`, lead ID `887`.
  - Overlapping referral enquiry ID count: `0`.
  - Strict booking / enquiry ID overlap count: `0`.
- Reporting rule:
  - Keep the two findings as separate diagnostic views.
  - Do not claim the `4` and `28` are the same records.
  - Do not casually add them as `32` independent customer-level issues.

### 2026-07-17 - Final Deliverables and Bilingual Word Reports

- Re-ran and verified:
  - `Referral_Bypass_Analysis/2_Booking_Centric_Bypass_Detection.ipynb`
  - Notebook error outputs: `0`.
- Final checked numbers:
  - Booking records: `5,275`.
  - Bookings with eligible prior referral: `20`.
  - Honored referral bookings: `16`.
  - Suspected booking-level bypass cases: `4`.
  - Same-enquiry attribution anomalies: `28`.
  - Same-enquiry anomaly leads: `7`.
  - Overlapping leads: `1`, lead ID `887`.
  - Strict booking / enquiry ID overlap: `0`.
- Generated desktop Word reports:
  - `/Users/jia/Desktop/referral_bypass_report_EN.docx`
  - `/Users/jia/Desktop/referral_bypass_report_ZH.docx`
- Copied reports and minimum review CSVs into:
  - `Referral_Bypass_Analysis/final_deliverables`
- Final deliverables:
  - `referral_bypass_report_EN.docx`
  - `referral_bypass_report_ZH.docx`
  - `referral_bypass_summary.csv`
  - `suspected_bypass_cases.csv`
  - `same_enquiry_attribution_anomalies.csv`
  - `overlap_summary.csv`
  - `overlap_by_lead.csv`
  - `overlap_by_referral_enquiry_id.csv`
  - `overlap_by_booking_or_enquiry_id.csv`
  - `compact_review_table.csv`
- Reporting position:
  - The `4` booking-level suspected bypass cases and `28` same-enquiry anomalies are two separate diagnostic views.
  - They overlap only at the lead level for `1` lead.
  - They should not be added into `32` independent customer-level issues.
- Report QA:
  - English DOCX rendered cleanly with the document workflow.
  - Chinese DOCX text was verified with macOS Quick Look because the headless LibreOffice renderer did not display Chinese glyphs reliably.
  - No PDF was generated, following the current delivery plan.

### 2026-07-17 - Markdown Report Becomes Submission Version

- Changed the main submission format from Word to Markdown.
- Added official Markdown report:
  - `/Users/jia/Desktop/referral_bypass_report.md`
  - `Referral_Bypass_Analysis/referral_bypass_report.md`
  - `Referral_Bypass_Analysis/final_deliverables/referral_bypass_report.md`
- The Markdown report keeps only the core explanation:
  - the business question;
  - the current matching rule;
  - Route 1: booking-level bypass check;
  - Route 2: same-enquiry attribution check;
  - why `4` and `28` are different;
  - overlap result;
  - review file list.
- Removed from the submission narrative:
  - Word/PDF process wording;
  - open questions section;
  - limitations / next steps section;
  - broad AI-style reporting-position wording.
- Current submission guidance:
  - Treat `referral_bypass_report.md` as the formal report / log.
  - Keep Word files only as previous draft artifacts; do not submit them unless specifically requested later.


### 2026-07-17 - Folder Cleanup

- Reorganized the project into three concise folders:
  - `data/raw` for original source tables and dataset guide.
  - `data/derived` for necessary exploration and review CSV outputs.
  - `code` for the two active notebooks.
  - `log` for AI change log and the formal Markdown report.
- Removed draft DOCX files, render images, checkpoint folders, duplicate reports, and old nested analysis folders from the active project tree.
- Original pre-cleanup folder was moved to backup:
  - `/Users/jia/Desktop/工作/Terra Softech/Terra Softech_2_backup_before_cleanup_20260717_165212`
