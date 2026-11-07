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

Fixed so far: invalid deal statuses are a 400 (c6cbe2f1), absences beyond
the shown weeks of the planning (3d76263d), the creator may undo absences
on the same day (57db358c).

### Verified bugs

Invoices, offers, services, logbook:

- Setting a cancelled services invoice back to sent leaves its logged
  entries released (`_unlink_logbook()`), the work can be invoiced again.
- The web interface creates offers on closed projects (`OfferForm`,
  `projects_project_createoffer`, probably `OfferCopyForm`); only the API
  refuses.
- Closing a project discards offers in preparation which have been sent
  before (`offered_on`), they should be declined like when closing deals
  (`discard_offers_in_preparation()`).
- Lines can be added to sent, paid or frozen invoices
  (`invoices_invoice_createservice`, no link in the UI).
- The logbook forms accept services of any project (the queryset isn't
  restricted), also of closed projects or with `allow_logging=False`.

Reports:

- Invoiced gross margin is negative when third party costs are logged
  before anything is invoiced; `not_in_planned_invoicing_excl_tax` (cash
  data) and the projected gross margin's delta then exceed the offered
  gross margin.
- The rate "only accepted offers" of `project_gross_margin()` takes the
  amount of budget retainer offers but the hours of the other offers.

Absences, planning, timer:

- The planning's batch update moves work to another project but keeps the
  old project's milestone (`PlannedWorkBatchForm.process()`).
- The planning context can't be imported unchanged when planned work
  belongs to a user with a blank short name (`"user": null`).
- `/create-timestamp/` (web timer) accepts closed projects, the API doesn't.

Contacts, deals, notes:

- The full text search of people lost organization, email addresses,
  phone numbers and postal addresses (`projects/0030_search_fix` redefined
  the trigger without `_fts`).
- `substitute_with()` and renaming organizations leave stale `_fts` of
  projects, deals, offers, invoices and people.
- Merging people or changing their organization leaves deals, projects and
  invoices whose contact doesn't belong to their customer; they can't be
  saved anymore. The "organization-update" warning of the person form
  ignores deals.
- Deals with probability `UNKNOWN` can't be PATCHed without `probability`.
- Notes in the web interface check neither features nor the allowed
  targets (add, update, delete), the API does.
- `DealForm` crashes on `?contact=`/`?customer=` when editing a deal.

API and wb:

- `ignore_warnings` is missing for absences, deal status and people
  creation; `wb` suggests `--ignore-warning` where it doesn't exist.
- `wb invoices pdf`/`wb offers pdf` crash on the 422 when the PDF can't be
  generated (`detail` is a string).
- 500s: Unicode digits as offer IDs or groups (`str.isdigit()`), groups
  with numeric titles can't be found by title, `Infinity` in the offers
  API, periods/dates out of range (`period=0000`, `9999-12`), unbounded
  timestamp `minutes`.

### Need a decision

- `services-invoiced-already` (ea95a99f) fires on every regular invoice
  from the logbook; the danger is switching between offer and logbook.
- Invoiced gross margin with logged third party costs and nothing invoiced
  (see above): deduct only up to what has been invoiced?
- Budget retainers in the rate "only accepted offers".
- Changing a person's organization moves the old organization's industry
  groups to the new one (`_save_organization_groups()`).
- The offer pricing form and `OfferForm` change the services of sent and
  accepted offers (only a warning), the project's `ServiceForm` and the
  API don't allow it.
- Future planned work of closed projects stays (capacity, needs action);
  planned work and milestones can be added to closed projects.

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
- The planning changes mail shows the old description when the reason was
  changed from sickness to another reason.
- Merging people loses groups of the duplicate's organization.
- Reassigning primary contacts restarts the archiving clock.
- Turning `applies_to_organizations` on also moves archived people.
- The notes digest and the Brevo sync ignore features and archived groups.
- Reopened deals keep their settled offers.
- Key data API: `accruals` and `gross_margin` of the same month may differ.
- The project detail labels the other side of retainer offers as third
  party costs; the budget chart adds both sides.
