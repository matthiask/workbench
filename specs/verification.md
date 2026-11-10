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
- Recurring invoices may mark their invoices as sent directly
  (`mark_as_sent`, off by default, never the standard behaviour). Payments
  are only assigned to sent invoices again (round 4: invoices in preparation
  became unsavable without a due date, and recurring invoices can create
  sent invoices now).
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
- `LATE_LOGGING` means that the hours of the person who has the feature
  (`rendered_by`, whoever enters them) can be logged late: logging them in
  past weeks and changing their hours and date there. Logged costs aren't
  affected and have no week lock (until they're archived or invoiced, or
  14 days after the project was closed). Deleting hours follows the same
  rule as changing them.
- Absences can't span the year end, so vacations across it are two
  absences.
- Statuses and probabilities are stable keys in the API (`workbench/api_keys.py`).
- The tax amount is the total minus the total excl. tax, so it absorbs the
  rounding to 5 cents (no rounding line).
- The planned gross margin of the year (Hochrechnung "Geplant") is the
  gross margin so far plus the projections not invoiced yet.
- Past years' absences are locked by the absent person's `LATE_LOGGING`:
  the feature is for people who don't log themselves, someone else is
  responsible; personnel administration doesn't matter.
- `hours_for_invoicing` isn't editable on projects closed > 14 days ago.
- Planned work of closed projects doesn't get weeks after the current one.
- Declining a deal only asks about planned work of the offers declined.
- Accepting offers of closed projects (through deals or the offer form) is
  fine.
- `wb people create` reports archived people with the same name and
  organization (or both without).
- Changing a deal's owner adds the new one to the contributions; the API
  and `wb deals update --contribution` change them.
- The budget statistics' cleanup filters don't combine with the closed
  projects or other cutoff dates (cleanup vs. reporting).
- Absences on a weekend count in their week.
- The annual working time keeps scaling partial months by calendar days:
  changing balances needs a lot of consideration (short partial months
  with holidays can have a negative target).

## Round 4 (2026-11-08)

Four agents (invoices/offers/logbook, reports, time, contacts/deals/API).
Fixed: margin per FTE by calendar quarter, invoiced services in the offer
pricing form, the old offer service API and the offer form, auto dunning
without contact, batch assignment of credit entries, blank short names in
the APIs, malformed parameters of the annual working time, offers given when
closing deals without related offers, recurring invoices in the merge
warning (the commits after "Verification: Findings of the fourth round").

### Decided

- Invoice lines know whether they were invoiced from the offer
  (`from_offer`, backfilled: lines without linked entries, and lines which
  still have the offered hours and cost and don't sum up their entries);
  invoicing the logbook warns about them.
- Changing the reason of a sickness absence while keeping the description
  is an error with a link to a new absence without the description, which
  replaces the old one.
- The Hochrechnung only extrapolates what is dated up to today.
- Request bodies reject unknown fields (`InputSchema`).
- Invoiced services may move between the offers of their project (offer
  form and service form): reassigning their logbook entries already moved
  the work and left empty services behind which couldn't be deleted.
- Deleting offers stays as it is: invoiced services lose their offer
  (`SET_NULL`), the services of a deleted declined offer become budgeted,
  and all planned work of the offer is deleted, past weeks too. Whether
  that's right depends on how the services were invoiced (deleting may be
  fine when invoicing from the logbook) and on whether the planned hours
  have been logged or invoiced; not worth the complexity for now.

### Ideas

- Contact details could be sorted explicitly (drag and drop, handles always
  visible) instead of weights by type; merging would then put the kept
  person's details first.
- Revisit anonymizing users after about ten years: there may be no reason
  to keep their data after that.

### Risks and questions, done

Fixed (the commits after "Verification: Deleting offers stays as it is"):
budget transfers beyond the accepted offers warn, the key data API computes
the month in progress as of today, the budget statistics' third party costs
at past cutoff dates, cash data rejects future dates, the squeeze XLSX
totals row, no future `work_completed_on`, payments only for sent invoices,
deleting invoice lines warns about the service period, down payments
exceeding the invoice warn, auto dunning sums totals incl. tax, external
work on closed projects, inactive users' timer tokens, archived value types
and attribute groups in the deals API, audit log pruning of data tables,
query parameter descriptions and a `wb deals show` test, cancelled invoices
don't make services invoiced, a new deal owner takes over the old owner's
contribution, the `wb people update` help.

Decided, no change:

- `clear_sickness_descriptions()`: absences can't be changed away from
  sickness with a description anymore (5c494f48); the history of emptied
  descriptions is pruned with the audit log.
- Merged contact details keep the weight of their type (see the idea above).
- Credits don't carry the third party costs of the credited invoice: key
  data keeps deducting them, which underestimates the gross margin (squeeze
  floors at 0).
- Changing a project's customer changes the customer of its invoices, also
  sent ones (a warning); their documents (postal address) stay as they are.
- "School attendance of apprentices" counts as working time without
  confirmation (apprentices have a special status, no weekly approvals);
  HR's own paid leave is confirmed automatically; paid leave descriptions
  are public.
- `POST /api/deals/` adds only the owner as contributor (you by default).
- The timer token endpoints stay: the controller uses them.
