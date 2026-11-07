# Verification rounds

Open findings of the verification rounds (see `AGENTS.md`), removed when
they're fixed or decided.

## Round 1 (2026-11-07)

### Verified bugs

- **Optional services' third party costs** are subtracted from the offered
  gross margin (`accepted_offers_by_project()` in
  `workbench/reporting/utils.py` sums all services of accepted offers, the
  offer total leaves optional ones out). Affects squeeze, profitability,
  cash data's `not_in_planned_invoicing_excl_tax`.
- **Cancelling an applied down payment** keeps it deducted from the final
  invoice (`down_payment_applied_to` and the final invoice's
  `down_payment_total` stay, `Invoice.save()`); the amount vanishes from
  revenue. Moving it back to "in preparation" likely the same.
- **"Final invoice, close the project"** in the invoice creation form only
  sets `closed_on` (`workbench/invoices/forms.py`), without
  `discard_offers_in_preparation()` and the planned work question of
  `ProjectForm`.
- **Logbook batch update** moves archived entries and entries of closed
  projects (`LogbookBatchForm`, `logbook_batch_update`), which
  `LoggedMoveForm` refuses. No tests.
- **Squeeze drops a project's period margin** when all hours in the period
  have `hours_for_invoicing=0` (`if total_weighted_in_range and hours`,
  `workbench/reporting/squeeze.py`).
- **Invoicing from the logbook lists already invoiced costs** and hours of
  services without a rate (all-time totals, `workbench/invoices/forms.py`
  around the services filter). Display only.
- **API updates of projects and deals without a contact** fail with "No
  contact selected." (warnings become errors, no override), closing
  included.
- **Search gates deals with `CONTROLLING`** instead of `DEALS`
  (`workbench/search.py`).
- **`null` in planned work updates** (PATCH and import entries with `id`)
  crashes with a 500 for `user`, `weeks`, `planned_hours`
  (`_apply_planned_work()`).
- **Internal projects can't be created through the API** with
  `INTERNAL_TYPES`: `ProjectIn`/`ProjectPatch` have no `internal_type`.
- **Last service of an offer**: `DELETE /api/services/<id>/` deletes it,
  the old offers endpoint refuses (the web interface allows it).
- **Planning capacity counts a day twice** when a public and a company
  holiday share the date (`workbench/planning/reporting.py`, also the
  displayed holiday rows); the AWT caps at one day.
- **Working time corrections reduce planning capacity** and show up as
  absences in the planning (capacity SQL, `add_absences()`); the planning
  context API and mails exclude them. `docs/metrics.md` says all reasons
  count.
- **Splitting a timestamp** drops project and service for all new parts
  (`split_timestamp`, `workbench/timer/views.py`).

### Untested risks

- Un-cancelling an invoice keeps `down_payment_total` while its down
  payments may have been applied elsewhere since.
- Editing an applied down payment doesn't update the final invoice's
  `down_payment_total`; services invoices keep a stale value when their
  down payments become ineligible.
- Moving a service without offer to another project takes its invoiced
  hours along, without a warning (`ServiceMoveForm`).
- Invoicing from the offer after invoicing from the logbook (or the other
  way round) gives no warning.
- Entries with `hours_for_invoicing=0` are never archived when invoicing
  from the logbook if their service has nothing else to invoice.
- Archived hours can still change service and hours (behind a warning).
- Recurring invoices ignore their own `tax_rate` (commented out).
- Rejected writes of read only tokens still extend them.
- Versions like `0.20.0rc1` parse to `()` and are "too old"
  (`workbench/cli_version.py`, `cli/wb/core.py`).
- Timestamps accept closed projects and services without logging; a
  numeric search term is always taken as an ID.
- Duplicate email addresses or phone numbers within one request aren't
  detected.
- `filter_users()` reports "Unknown users" for a user outside the team.
- `{"applies_to_organizations": null}` turns the flag off.
- `SetStatusForm` reads `?status=` from the query string (API too) and
  crashes on non-numeric values; re-closing a deal moves `closed_on` to
  today.
- Planning import fails when an LLM echoes inactive users or declined
  offers of the context back unchanged.
- `clear_sickness_descriptions()` misses history of absences whose
  description was cleared or reason changed.
- Closing a deal preselects linked offers in preparation, which can't be
  declined ("Offered on date missing").

### Questions (decisions)

- API: should PATCH endpoints get a `force` to ignore warnings like the web
  interface (missing contact, customer changed, reopening)?
- May the last service of an offer be deleted (both endpoints and web)?
- Reopening a project: restore discarded offers?
- Deleting/cancelling a services invoice: undo `disable_logging`?
- Key data's cancelled invoices include those never sent?
- Recurring invoices with `create_project`: close the projects?
- Project flat rate for services of service groups?
- Invoice creation help text sums all accepted offers instead of the
  retainer-or-other rule.
- Reordering services of sent/accepted offers is allowed.
- Services may be created on closed projects, offers not.
- Service groups can't be renamed through the API.
- `/api/projected-invoices/` requires `CONTROLLING`, the web view
  `PROJECTED_GROSS_MARGIN`.
- Duplicate group titles: enforce in `GroupForm` too?
- Turning `applies_to_organizations` off drops the members through
  organizations.
- Merging people into an archived person keeps it archived.
- Merging organizations drops the groups of the deleted one.
- Archiving unused contacts: deals count by creation, projects by closing.
- Reassign suggestions prefer the own project over a newer own deal.
- Non-admins may edit and delete others' non-sickness absences.
- Admins editing unconfirmed paid leave confirm it implicitly.
