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
