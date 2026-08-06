# Referral Attribution Metric Dictionary

**Primary reporting mode:** strict attribution  
**Primary analysis grain:** one non-canceled booking  
**Configuration source:** [`config/attribution_rules.json`](../config/attribution_rules.json)

## Source Tables

| Source | Grain | Main role | Important limitation |
|---|---|---|---|
| `referral_submissions.csv` | One referral enquiry | Identifies who referred a lead, when, and for which project | Same-enquiry booking dates contain reverse-time records |
| `booking_extracts.csv` | One non-canceled booking | Identifies the final booking source and linked lead/project | Some bookings have no usable enquiry or lead identity |

## Core Definitions

| Term | Plain-language definition | Technical calculation | Input grain | Output grain | Exclusions | Known limitation |
|---|---|---|---|---|---|---|
| Primary identity key | The default rule for deciding that a referral and booking belong to the same person | Exact equality on normalized `client_name` and `lead_id` | Referral enquiry + booking | Candidate pair | Null lead IDs; different clients | A reused or incorrect lead ID can still create ambiguity |
| Secondary identity route | A separate identity-confirmation queue when the primary lead-ID route does not cover the booking | Exact encrypted `mobileNumber` or `email` equality within the same client | Referral enquiry + booking | One Tier C row per booking | Bookings already covered by the primary route; null keys | Exact equality is evidence, not confirmed identity; encrypted values are never exported |
| Booking timeline | The date used to order a booking against a referral | Use `bookingDate`; if missing, use `booking_created_on` | Booking | Booking | Unparseable dates | Created time is a fallback and may differ from the business event date |
| Eligible prior referral | A referral that can legally precede the booking in the attribution analysis | Same primary identity and `referral_submitted_at <= booking_timeline_at` | Candidate pair | Candidate pair | Test/demo rows; reverse-time pairs | No approved maximum business window exists |
| Latest prior referral | The selected referral when a booking has multiple eligible prior referrals | Sort by booking, referral time, and referral ID; keep the latest row | Eligible pair | One row per booking | Referrals outside a sensitivity window, when a window is tested | Latest referral does not prove commission ownership when multiple referrers exist |
| Strict honored | The primary evidence that the booking was credited to referral | `booking_source == "REFERRAL"` after source normalization | Booking | Booking | None beyond the filtered analysis base | Shows recorded source, not commission eligibility or payment |
| Primary review candidate | A time-valid primary match not honored under the strict rule | Latest eligible exact-lead match where `honored_strict == False` | Booking | One row per booking | Test/demo rows; reverse-time; Tier C | It is a review candidate, not proof of fraud or commission loss |
| Test/demo exclusion | Removes clearly non-production names before primary analysis | Configured regex across lead/referrer name fields | Referral enquiry or booking | Filtered source row | `test`, `demo`, `dummy`, `sample`, `training`, `internal`, and explicit test prefixes | Name-based filtering may miss undocumented internal records |
| Tier A | A primary review case with one prior referrer and no timeline ambiguity | Primary candidate, `prior_referrer_count == 1`, no timeline ambiguity | Booking | One review row | Honored cases | Still requires source-system verification |
| Tier B | A primary review case with ambiguous ownership or chronology | Primary candidate with multiple prior referrers or timeline ambiguity | Booking | One review row | Honored cases | Cannot identify the rightful referrer from these extracts alone |
| Tier C | A secondary exact-identity match outside the primary lead-ID route | Exact mobile/email equality, same client, prior referral, booking not covered by lead-ID route | Booking | One review row | Primary-route bookings | Identity confirmation is required before attribution review |
| Data Integrity | A record requiring source-data repair rather than bypass review | Invalid chronology, missing critical date, or contradictory source evidence | Referral enquiry | One issue row | Excluded from the primary bypass denominator | Repair may change later attribution evidence |
| Reverse-time case | A same-enquiry booking dated before its referral submission | `booking_on_referral_at < referral_submitted_at` | Referral enquiry | One issue row | Never enters the primary queue | Could be an extract mapping, timezone, backfill, or source-system problem |
| Attribution window | Maximum allowed days between a referral and booking in a sensitivity view | `days_between_referral_and_booking <= 30/60/90/180`; unlimited is primary | Eligible pair | One row per booking | Pairs outside the tested window | No official business window has been approved |
| Same-project match | The selected referral and booking point to the same project | `booking_project_id == referral_project_id` | Selected match | Booking | None | Project equality does not resolve ownership |
| Cross-project match | The selected referral and booking point to different projects | `booking_project_id != referral_project_id` | Selected match | Booking | None | The dataset guide keeps cross-project cases in scope |
| Multiple-referrer share | Portion of eligible bookings with more than one distinct prior referrer | Eligible bookings with `prior_referrer_count > 1` divided by all eligible bookings | Selected match | Summary | Test/demo; reverse-time | High counts require manual ownership review |
| Agreement value | Context on the transaction size | Parsed numeric `agreementValue` from the booking extract | Booking | Review row | Missing or non-positive values are flagged | Not commission amount, loss, margin, or recoverable impact |

## Required Headline Metrics

| Metric | Recompute from | Denominator |
|---|---|---|
| Eligible bookings | Unique `booking_id` in latest time-valid primary matches | Filtered bookings for base-rate context |
| Strict honored bookings | Eligible bookings where `honored_strict` is true | Eligible bookings |
| Primary review candidates | Eligible bookings where `honored_strict` is false | Eligible bookings |
| Tier B count | Primary review rows labeled Tier B | Primary review candidates |
| Tier C count | Unique Tier C booking IDs | Secondary review queue only |
| Reverse-time source disagreements | Reverse-time same-enquiry rows with referral/non-referral source disagreement | Reported outside the bypass denominator |
