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

### Decided, no change

- Changing a person's organization carries the industry groups shown in the
  form over to the new organization.
- The invoiced gross margin is never negative, also when third party costs
  have been paid before invoicing (see `docs/metrics.md`).

### Untested risks

- Deleting accepted or invoiced offers (no status check).
- Services invoiced from the offer without logged entries can be moved or
  deleted, the invoice line then points elsewhere or nowhere.
- Projected invoices check neither `FreezeDate` nor closed projects.
- Reactivated recurring invoices create the whole backlog in past periods.
- Milestones with `phase_starts_on` after `date`; moving milestones earlier
  through the import doesn't warn about later work.
- Overlapping absences aren't detected.
- The annual working time uses the current working time model for past
  years; absences outside employments count.
- Merging people loses groups of the duplicate's organization.
- Reassigning primary contacts restarts the archiving clock.
- Turning `applies_to_organizations` on also moves archived people.
- The notes digest and the Brevo sync ignore features and archived groups.
- Reopened deals keep their settled offers.
- Key data API: `accruals` and `gross_margin` of the same month may differ.
- The project detail labels the other side of retainer offers as third
  party costs; the budget chart adds both sides.
- The groups API and the services API ignore all warnings of their forms
  (`is_valid(ignore_warnings=True)`), unlike the other endpoints.
- `/api/planning/export/` with a range of centuries builds every week (slow,
  no crash).
