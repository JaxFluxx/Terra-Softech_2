# Referral Attribution: Week 5 Decision Memo

## 1. Situation

The accepted analysis finds a small primary attribution-review queue, but a much larger chronology problem. The decision is therefore not whether the data proves referral bypass. It is how to review the current cases, prevent avoidable source overrides, and repair the evidence needed for future attribution decisions.

## 2. Method and Assumptions

- Removed explicit test/demo records: referrals `5,448 -> 4,585`; bookings `5,275 -> 4,713`.
- Matched on exact `client + lead_id`.
- Required `referral_submitted_on <= bookingDate`, using `booking_created_on` only when the business date is missing.
- Selected the latest eligible prior referral.
- Used one primary honored definition: `booking_source == "REFERRAL"`.
- Compared 30/60/90/180-day and unlimited attribution windows as sensitivity checks.
- Treated `agreementValue` as transaction context, not commission impact.

## 3. Findings That Change the Decision

- `4,062` filtered bookings share client and lead identity with at least one referral, but only `12` have a referral that occurred before the booking. This is a chronology and lifecycle-data bottleneck, not a conversion-rate conclusion.
- Of the `12` eligible bookings, `8` are strictly honored and `4` require primary review.
- All `4` primary cases are **Tier B** because each has multiple prior referrers; one also has a timeline ambiguity. The four booking IDs remain `1206`, `935`, `3331`, and `4913`.
- The primary review count stays at `4` under 30-, 60-, 90-, 180-day, and unlimited windows.
- `28` same-enquiry source disagreements are reverse-time. They belong in Data Integrity, not in the primary bypass denominator.
- `3` exact encrypted-mobile matches form a separate Tier C identity-confirmation queue. They do not change the primary count.

## 4. Recommendation

### Ops: act this week

1. Validate the date semantics and linked-record history for the `28` reverse-time records before using them as referral-conversion evidence.
2. Review the `4` Tier B bookings in the source CRM, focusing on which prior referrer owned the referral and whether the recorded booking source is correct.
3. Confirm identity for the `3` Tier C records before any attribution decision.

The sortable queue is [`ops_review_board.csv`](../data/derived/ops_review_board.csv).

### Product: add one controlled workflow check

Propose a **30-day referral-history warning** when a booking is about to be saved with a non-referral source:

- show the latest prior referral and all prior referrers;
- require the user to confirm the owner or record an override reason;
- send multi-referrer cases to manual review rather than assigning automatically.

This is a proposed operating rule, not a confirmed commission policy. The batch analysis should continue to retain the unlimited-window sensitivity view.

### Data: repair the evidence layer

- Investigate why `4,050` identity-overlap bookings have only later referrals and confirm what the `booking_on_referral_*` fields represent for the `28` reverse-time links.
- Where the system supports it, add monitored fields for event timestamp provenance, source-change history, and override reason.
- Use the strict booking-source metric for attribution reporting and monitor enquiry/booking source disagreements separately as data-quality evidence.

## 5. What Is Not Proven

- The four primary cases are not confirmed fraud, confirmed bypass, or confirmed commission loss.
- The rightful referrer cannot be determined from the extracts when many prior referrers exist.
- Agreement value cannot be converted into commission impact without eligibility, rate, reversal, and payout data.
- The test/demo filter and proposed 30-day workflow window still need business-owner confirmation.

## 6. 30/60/90-Day Measurement Plan

| Horizon | Leading indicator | Guardrail | Falsifier |
|---|---|---|---|
| 30 days | Share of non-referral bookings checked before confirmation; age of open P0/P1 cases | Booking completion time and override volume | Most warnings are validated as correct non-referral bookings or cannot identify an owner |
| 60 days | Share of warnings resolved before booking completion; repeat reverse-time volume | Manual-review backlog and false-escalation rate | Queue volume grows without clearer date semantics or source evidence |
| 90 days | Strict honored rate among time-valid eligible bookings; unresolved multi-referrer share | Source disagreement and missing timestamp rates | Attribution evidence does not improve after date-semantic validation and workflow checks |
