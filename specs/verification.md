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

Four agents (invoices, reports, time, contacts/deals/API). The verified bugs
have been fixed (the commits after "Verification: Findings of the third
round"), except the one below.

### Decided

- Closing a deal only preselects offers in preparation or offered; settled
  offers (also of reopened deals) only when selected.
- Squeeze deducts absence days as full days from the employment's working
  days (like the annual working time).
- Invoicing an offer doesn't preselect optional services (from the logbook
  they are, work has been logged on them).
- The key data API leaves out deals and squeeze without their features.
- Payments may be assigned to invoices in preparation with a date after the
  freeze date (useful, see 06fb06cd); recurring invoices may mark their
  invoices as sent directly (`mark_as_sent`, off by default).

### Open bug

- Logged hours without timestamp created a day after `rendered_on` produce a
  ~15h detected slice on that day (`timer/models.py`, entries are placed at
  their `created_at`). Needs a decision where they belong in the timeline.

### Untested risks

- Services without offer (or in preparation) can be repriced after being
  invoiced from the logbook (flat rate, `ServiceForm`), changing past
  budget statistics and accruals.
- Unsent projections mail: "Fremdkosten" = invoiced − gross margin is wrong
  since the invoiced gross margin is clamped at 0 (`invoices/tasks.py`).
- Credits through the API silently drop `discount`, `third_party_costs`.
- PDF totals have no rounding line (up to 0.04 difference).
- Annual working time: short partial months can give a negative target.
- Planning display vs capacity disagree about absences on weekends.
- Absence web form accepts zero or negative days (API requires > 0).
- Planning import deleting a milestone referenced by work in the same
  import nulls the milestone silently.
- Planning export with only `project`/`campaign` skips the ten-year check.
- Accepting a deal accepts offers on closed projects.
- `project_update` with `closed_on` adds `messages.info` (also `dry_run`).
- `person_create` duplicate checks ignore archived contacts; new
  organizations get the current user as primary contact.
- Changing a deal's owner keeps the old owner's weight.
- `labor_costs.py` divides by `green_hours_target` (0 possible in admin).
- Average employment duration: future and fixed-term employments skew it.
- Budget statistics `old-projects`/`no-projected-gross-margin` use today's
  `open()` with past cutoffs and `closed`; API sorts closed by delta.

### To decide

- Recurring invoices with `create_project` stay accruals forever.
- The offer's discount isn't carried over when invoicing an offer.
- Third party costs of frozen invoices and projections in frozen periods
  stay editable.
- Unassigning a payment leaves the invoice PAID.
- Green hours: projects whose budgeted services add up to 0h count all
  hours as overdrawn.
- Team filters use the current membership for past periods.
- Hochrechnung "Geplant" adds projections to the extrapolated year.
- Past years' absences are locked by the absent person's `LATE_LOGGING`.
- `hours_for_invoicing` isn't editable on projects closed > 14 days ago.
- Logged costs have no week lock when deleting; logged hours of past weeks
  can't be deleted by `LATE_LOGGING` users.
- Declining offers / closing deals delete all planned work, closing
  projects only the future.
- Planned work on closed projects can still be moved.
- Vacations across the year end can't meet the two weeks check.
- API outputs localized `status`/`probability`, inputs take codes.
- `delete_planned_work` is required when declining with `offers: []`.
