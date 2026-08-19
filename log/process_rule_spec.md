# Booking Referral-History Warning: Process Rule Specification

## Goal

Prevent an avoidable attribution miss when a user saves a booking as a
non-referral source despite recent referral history. This is a warning and
review workflow, not an automatic commission engine.

## Trigger and Lookup

- Trigger: booking create or source update where the proposed source is not
  `REFERRAL`.
- Lookup: exact `client + lead_id`, using referral records submitted within the
  configured 30-day product window.
- Display: latest referral, count of prior referrers, and up to the configured
  cap of five referrers for the user interface.
- Batch analysis: retains unlimited-window sensitivity separately; it does not
  inherit the 30-day user-interface rule as a default attribution limit.

## Decision Table

| Referral history at save time | System behavior | Automatic ownership or payout? |
|---|---|---|
| No prior referral | No warning | No |
| One same-project prior referrer | Soft warning; show owner candidate | Owner candidate only, no payout decision |
| Two or more same-project prior referrers | Soft warning; require override reason; create manual review | No |
| Cross-project referrals only | Low-severity warning; write event | No |
| Proposed source already `REFERRAL` | No warning | No new decision needed |

## Pseudocode

```text
on_booking_save(proposed_booking):
    if proposed_booking.source == REFERRAL:
        continue_without_warning()

    history = find_referrals(
        client=proposed_booking.client,
        lead_id=proposed_booking.lead_id,
        submitted_on_or_before=proposed_booking.timeline,
        within_days=30,
    )

    if history.is_empty:
        continue_without_warning()
    elif history.has_same_project and history.distinct_referrer_count == 1:
        show_soft_warning(latest_referral=history.latest)
    elif history.has_same_project:
        require_override_reason()
        create_manual_review(history)
    else:
        show_low_severity_warning()

    write_event(booking, history, user_action, override_reason)
```

## Required Event Fields

`event_name`, `event_version`, `booking_id`, `user_id`,
`booking_source_proposed`, `referral_history_snapshot`, `policy_id`,
`warning_shown`, `warning_severity`, `override_reason_code`,
`override_reason_free_text`, `prior_referrer_count`, `window_days`,
`decision`, and `timestamp`.

The implementation should retain the minimum necessary event data, apply the
company's consent and retention requirements, and avoid copying raw referral
history into unrelated logs.

## Pilot Guardrails

- Phase 1 is a soft warning. A hard stop is out of scope until pilot data shows
  it improves attribution without harming booking completion.
- Multiple referrers always remain manual in the pilot.
- Cross-project history can prompt review, but it cannot trigger an automatic
  payout.
- Reverse-time records are not evaluated by this workflow until chronology is
  repaired.
- In the current historical simulation, all four baseline Tier B bookings have
  a 30-day referral-history warning. Three remain multi-referrer escalations;
  one becomes a single-referrer soft warning after the 30-day recount.
