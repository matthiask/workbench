# Verification rounds

Open findings of the verification rounds (see `AGENTS.md`), removed when
they're fixed or decided.

## Round 1 (2026-11-07)

### Decided, no change

- Reopening a project doesn't restore its discarded offers.
- Deleting or cancelling a services invoice doesn't undo `disable_logging`.
- Recurring invoices with `create_project` aren't closed automatically (see
  the journal note about closing projects automatically).
- Entries with `hours_for_invoicing=0` stay unarchived if their service has
  nothing else to invoice.
- CLI versions are plain numbers (`0.29.0`), no pre-releases.
- The history of sickness absences is only visible with
  `PERSONNEL_ADMINISTRATION` and pruned after three years.
- Services can still be created on closed projects (documented as a known
  gap in `AGENTS.md`).

### Data

- 2023-0161 has a flat rate (166) but six services of service groups at
  140/180 (since ae288a6c, saving the project applies the flat rate to
  them too).

## Round 2 (2026-11-07)

All verified bugs have been fixed and the decisions implemented (see the
commits of 2026-11-07 after "Verification: Findings of the second round").
The untested risks have been tested and fixed or decided too (the commits
after "Verification: The second round's bugs are fixed").

### Decided, no change

- Changing a person's organization carries the industry groups shown in the
  form over to the new organization.
- The invoiced gross margin is never negative, also when third party costs
  have been paid before invoicing (see `docs/metrics.md`).
- Merging people doesn't carry over the industry groups of the duplicate's
  organization: they describe that organization.
- Reassigning primary contacts to active users counts as use of the contact
  (it keeps them from being archived).
- Overlapping absences aren't detected: a vacation day on a sickness day
  uses up the vacation day and counts the sickness, which evens out in the
  balance. Duplicate sickness entries don't, and the planning capacity of
  that week is too low.
- The annual working time uses the user's current working time model for
  past years; changing a user's model rewrites them. Moving the model to
  the employments waits for a real case (models changing during the year
  complicate the computation).
- Last month's key data are final after the fairy tasks have run in the new
  month (documented in `docs/metrics.md`).
- Turning `applies_to_organizations` on also moves the memberships of
  archived people to their organizations, which keeps the rule that only
  people without an organization are members themselves.
- Moving milestones earlier through the planning import only warns about
  the work in the import; the `workbench-planning` skill checks the rest.
- The groups form has no warnings, so its API skips nothing.

## Round 3 (2026-11-07)

Four agents (invoices, reports, time, contacts/deals/API), then two agents
testing the untested risks. The verified bugs and the real risks have been
fixed (the commits after "Verification: Findings of the third round").

### Decided

- Closing a deal only preselects offers in preparation or offered; settled
  offers (also of reopened deals) only when selected.
- Squeeze deducts absence days as full days from the employment's working
  days (like the annual working time).
- Invoicing an offer doesn't preselect optional services (from the logbook
  they are, work has been logged on them) and starts with its discount.
- The key data API leaves out deals and squeeze without their features.
- Payments may be assigned to invoices in preparation with a date after the
  freeze date (useful, see 06fb06cd); recurring invoices may mark their
  invoices as sent directly (`mark_as_sent`, off by default, never the
  standard behaviour).
- Hours logged on another day than they were rendered on are listed at the
  end of the day, outside the timeline.
- Declining offers and deals deletes only the planned work after the current
  week, like closing projects (full-year reservations may have to be redone).
- Third party costs stay editable in frozen invoices and projections:
  incorrect third party costs make the reporting incorrect.
- Recurring invoices with `create_project` stay accruals as long as their
  projects are open; people should close them, this will be fixed another
  way.
- Unassigning a payment leaves the invoice paid (bookkeeping notices), the
  form warns.
- Green hours: projects whose budgeted services add up to 0h count all hours
  as overdrawn. Taking invoiced hours into account would rebuild squeeze.
- Team filters use the current membership, also for past periods.
- `LATE_LOGGING` doesn't treat logged costs and logged hours differently, by
  design.
- Absences can't span the year end, so vacations across it are two
  absences.
- Statuses and probabilities are stable keys in the API (`workbench/api_keys.py`).
- The tax amount is the total minus the total excl. tax, so it absorbs the
  rounding to 5 cents (no rounding line).

### To decide (need more information first)

- Hochrechnung "Geplant" adds the year's projected gross margin to the
  extrapolated year.
- Past years' absences are locked by the absent person's `LATE_LOGGING`, not
  the editor's.
- `hours_for_invoicing` isn't editable on projects closed > 14 days ago.
- Planned work on closed projects can still be moved.
- `delete_planned_work` is required when declining a deal with `offers: []`.
- Accepting a deal (or the offer form) accepts offers of closed projects.
- `wb people create` doesn't report archived people and organizations with
  the same name (they could be unarchived instead).
- Changing a deal's owner keeps the old owner's contribution (handing over
  vs. adding a contributor); the API can't change contributions.
- Budget statistics filters `old-projects` and `no-projected-gross-margin`
  use today's state with past cutoff dates and the closed filter.
- Weekend-only absences: planning shows a single day without `ends_on` in
  the following week, the capacity drops it; Saturday to Sunday appears in
  neither.
- Annual working time: partial months scale the target by calendar days but
  subtract holidays in full, so short partial months can be negative
  (employment January 1–2 with two holidays). Scaling by weekdays would fix
  it but changes the balances of people who started or left mid-month.
