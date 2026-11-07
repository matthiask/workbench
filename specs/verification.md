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

Four agents (invoices, reports, time, contacts/deals/API). Bugs were shown
with throwaway tests; the cited code has been checked unless marked
"unchecked".

### Verified bugs

Invoices and payments:

- Assigning a payment (`CreditEntryForm.save()`,
  `AssignCreditEntriesForm.save()`, `credit_control/forms.py`) sets
  cancelled invoices to PAID; their released entries and down payments can
  be invoiced again.
- `AssignCreditEntriesForm` offers invoices in preparation
  (`Invoice.objects.open()`) and sets them PAID without `invoiced_on`.
- Sent invoices which aren't frozen can be backdated into the frozen period
  (`invoices/forms.py`, freeze check only for `_orig_status < SENT`).
- `Invoice.objects.overdue()` includes credits: sent credits go to dunning,
  autodunning and "needs action".
- `_round_5cents()` (`tools/models.py`) rounds half to even: 25.00 + 8.1%
  = 27.025 gives 27.00 instead of 27.05.
- Invoicing an offer preselects its optional services, also in the API
  (`invoices/forms.py` `selected = ...`). Unchecked; maybe a decision.

Reports:

- Key data view: the `defaultdict` lambda uses the loop variable `month`;
  500 on empty data, and in early January without a row for the current
  month the year rows are labelled wrong (`reporting/views.py`).
- Team filters with an empty team show everyone: `green_hours.py`
  (`users or ...`), `projects/reporting.py` `hours_per_customer` and
  `hours_per_type` (`if users:`), `reporting/api.py` planning vs logbook.
- Squeeze scales absence days with the employment percentage
  (`(working_days - absence_days) * employment%`), unlike the annual working
  time and planning (`working_days * employment% - absence_days`). Doc
  matches the code; maybe a decision.

Time:

- `LoggedCost.allow_delete` shows the expense report error but doesn't
  return `False`.
- Copying a missing logged cost (`?copy=999999`) crashes: catches
  `LoggedHours.DoesNotExist` (`logbook/forms.py`).
- Planning import: updating a milestone resets `phase_starts_on` and
  `estimated_total_hours` when they're omitted (`planning/api.py`).
- External planning shows employment percentages in the text of public
  holidays (`planning/reporting.py` `add_public_holidays`).
- `delete_future_planned_work()` can leave planned work with 0.0 hours.
  Unchecked.
- Planned work more than ~77 weeks ahead can't be saved in the web form
  (week choices, `planning/forms.py`, also `ExternalWorkForm`). Unchecked.
- Planning update mails report moved planned work under the old project
  (`planning/updates.py` `project_for_action(actions[0])`). Unchecked.
- Logged hours without timestamp created a day after `rendered_on` produce a
  ~15h detected slice (`timer/models.py`). Unchecked.

Contacts, deals, offers:

- Closing a deal preselects offers with the opposite status (e76cbe35) even
  if another deal or the offer form settled them (`deals/forms.py`
  `SetStatusForm`).
- Closing a deal with a past `closed_on` dates the offers' `closed_on`
  today (`Offer.clean_fields`); reopened and settled again keeps the old
  date.
- Deleting an organization cascades to its `ExternalWork.provided_by`
  without offering a substitute (`planning/models.py`). Unchecked.
- `Offer.copy_to()` ignores the target project's flat rate and doesn't copy
  `postal_address` (the copy then fails `full_clean` in the offers API).

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
- Key data API returns accepted deals, funnel and squeeze gross margin with
  CONTROLLING only.
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
