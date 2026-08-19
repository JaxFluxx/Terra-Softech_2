# Multi-Referrer Policy Brief

## Decision

Use **P-MANUAL** as the provisional ownership policy for a 90-day pilot:

- Keep the latest time-valid referral as the detection reference.
- Auto-show an owner candidate only when there is exactly one distinct prior
  referrer.
- Require manual ownership review when there are two or more distinct prior
  referrers.
- Do not calculate or allocate commission from this dataset.

## Why the Policy Is Needed

The current primary review queue contains four Tier B bookings. Every Tier B
booking has multiple prior referrers, so chronology alone cannot establish who
caused the booking or who is payment-eligible.

## Unlimited Batch Comparison

| Policy | Clean one-referrer case | Four Tier B cases | Ops cost | Risk and additional evidence needed |
|---|---|---|---|---|
| P-LAST | Auto-show latest owner candidate | Auto-assigns all 4 | 0 manual cases | Latest timing is useful evidence, but does not prove contribution or eligibility. |
| P-FIRST | Auto-show first owner candidate | Auto-assigns all 4 | 0 manual cases | First timing has the same ownership limitation and needs an approved ownership rule. |
| **P-MANUAL** | Auto-show latest owner candidate | Manual review for all 4 | **5 manual cases; 7 auto-handled** | Recommended: source history and Ops review decide ambiguous ownership rather than chronology alone. |
| P-SAME-PROJECT-LAST | Auto-show latest same-project candidate when available | Auto-assigns all 4 | 0 manual cases | Project match is helpful context, but needs reliable project history and still does not prove ownership. |

The case-level comparison is exported in
`data/derived/multi_referrer_policy_case_matrix.csv`.

## Window Sensitivity

- The batch view remains unlimited so that historical attribution can be
  measured consistently.
- The product warning uses a 30-day window to avoid surfacing stale history in
  the booking flow.
- At 30, 60, 90, 180 days, and unlimited, the primary review count remains
  four. At the 30-day product window, all four baseline Tier B bookings
  (`935`, `1206`, `3331`, and `4913`) have referral history that would trigger
  a warning.
- Under a strict 30-day recount, `935`, `1206`, and `4913` still have multiple
  referrers and would escalate to manual review. Booking `3331` has only one
  referrer inside the 30-day window, so it would receive the single-referrer
  soft warning rather than a multi-referrer escalation.
- The manual-policy workload changes only because a few eligible one-referrer
  cases move in or out of the window.
- A stable review count is useful: the chosen policy is not being driven by a
  single arbitrary window. It does not prove that any window is a commission
  eligibility rule.

## Not Recommended

Do not use a recency-weighted or time-decay commission split. It can describe
proximity to a booking, but this dataset has no evidence of contribution,
eligibility, commission rate, payout, or reversal. It would create a financial
rule from unsupported assumptions.
