# Referral Attribution: Week 6 Decision Memo

## 1. Situation

The Week 5 pipeline identified a small booking-first review queue and a larger
chronology-quality issue. Week 6 extends that work into two decisions: how to
frame the workload honestly, and how the product should behave when a booking
has more than one prior referrer.

## 2. Method and Assumptions

- The primary route remains exact `client + lead_id`, with a referral required
  to occur on or before the booking timeline.
- The latest time-valid referral remains the **detection reference**. It is not
  treated as proof of commission ownership.
- A booking is honored only when `booking_source == REFERRAL` after source
  normalization.
- The default production-like base removes explicit name-pattern test/demo
  rows. Five additional booking rows match configured CRM-ID or unit-number
  signals and remain visible as a data-quality sensitivity.
- The default regression contract remains `12 eligible / 8 honored / 4 review`.
  The four review IDs are `1206`, `935`, `3331`, and `4913`. Enabling the JSON
  strong-signal switch is a separately tested sensitivity, not the active
  primary-funnel rule.
- `agreementValue` is retained only as transaction context. It is never
  presented as commission, loss, or recoverable impact.

## 3. Findings That Change the Decision

- The filtered production-like base contains `4,713` bookings. `4,062` share an
  exact client and lead ID with a referral, but only `12` have a time-valid
  prior referral. The large drop is a data-lifecycle finding, not a conversion
  conclusion.
- `8 of 12` eligible bookings are strictly honored. The remaining `4 of 12`
  are primary review candidates: `33.3%` within the qualified referral path.
- For routine Operations (Ops) workload planning, the same four cases equal
  `0.85` review cases per 1,000 filtered bookings. This is the headline
  workload metric; it is not a system-wide bypass rate.
- All four primary cases are Tier B because each has multiple prior referrers.
  The impact table exports the Tier B agreement-value sum, median, minimum,
  and maximum only as transaction context. One row has a repeated-digit
  `agreementValue` pattern (`11,111,111`), so the value needs verification
  without removing the attribution case.
- `28` reverse-time source disagreements remain a separate Data Integrity
  backlog, and `3` Tier C rows remain an identity-confirmation queue. Neither
  category enters the primary review count.

## 4. Recommendation

### Ops: use P-MANUAL for multi-referrer ownership

- For a booking with exactly one prior referrer, show the latest prior referral
  as an owner candidate.
- For two or more distinct prior referrers, use `P-MANUAL`: do not auto-assign
  ownership or payout; route the case to manual review.
- Under the unlimited batch view, `P-MANUAL` auto-handles `7` of `12` eligible
  bookings and manually reviews `5`, including all `4` Tier B review cases.
- Do not use first-referrer, latest-referrer, or same-project-only rules as
  automatic commission rules. Each would auto-assign all four Tier B cases
  despite the ownership ambiguity.

### Product: pilot a controlled 30-day warning

When a user saves a booking with a source other than `REFERRAL`, look back 30
days using the same exact identity route.

- No prior referral: no warning.
- One same-project referrer: soft warning and show one owner candidate.
- Two or more same-project referrers: soft warning, required override reason,
  and manual review.
- Cross-project history only: low-severity warning and event log; no automatic
  payout.

In the historical 30-day simulation, all four baseline Tier B cases would
receive a warning. Three retain multi-referrer escalation; one has a single
referrer within the shorter window and receives a soft warning instead.

Keep the unlimited view for batch sensitivity analysis. Do not introduce a hard
stop unless pilot evidence shows that warnings improve attribution without
creating unacceptable booking friction.

### Data: repair the evidence needed for future decisions

- Send the 28 reverse-time rows to data repair with timestamp provenance,
  booking/referral source history, and override reason where available.
- Add a value-sanity flag for keyboard-pattern or non-positive agreement values.
  The flag prompts verification; it does not suppress a review case.

## 5. What Is Not Proven

- The four primary cases are review candidates, not confirmed bypass, fraud,
  commission loss, or payment liability.
- These extracts cannot establish multi-referrer contribution or payout
  eligibility, so they cannot justify a time-decay commission split.
- The data cannot yet estimate financial impact without a commission rate,
  eligibility, reversal, and payout record.

## 6. 30/60/90-Day Measurement Plan

| Horizon | Leading indicator | Guardrail | Falsifier |
|---|---|---|---|
| 30 days | Warning display rate and override-reason completion | Booking completion time; missing reason rate | Most warnings are confirmed as valid non-referral bookings with no actionable owner evidence |
| 60 days | Manual-review resolution rate; median queue age | Unresolved multi-referrer backlog; false escalations | Manual review does not improve ownership evidence or creates an unsustainable queue |
| 90 days | Strict honored rate among eligible bookings; repeated reverse-time volume | Source disagreement rate; warning-to-review conversion | The warning changes neither recorded attribution nor data completeness |

The supporting outputs are `impact_framing_summary.csv`,
`multi_referrer_policy_sensitivity.csv`,
`multi_referrer_policy_case_matrix.csv`, and
`process_window_and_policy_sensitivity.csv`.
