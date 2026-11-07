# Verification rounds

Open findings of the verification rounds (see `AGENTS.md`), removed when
they're fixed or decided.

## Round 1 (2026-11-07)

### Verified bugs

- **Cancelling an applied down payment** keeps it deducted from the final
  invoice (`down_payment_applied_to` and the final invoice's
  `down_payment_total` stay, `Invoice.save()`); the amount vanishes from
  revenue. Moving it back to "in preparation" likely the same. Needs a
  decision about the process (forbid while applied, or fix up the final
  invoice, which may be sent or frozen already).

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
- `SetStatusForm` reads `?status=` from the query string (API too) and
  crashes on non-numeric values.
- Planning import fails when an LLM echoes inactive users or declined
  offers of the context back unchanged.
- `clear_sickness_descriptions()` misses history of absences whose
  description was cleared or reason changed.
- Closing a deal preselects linked offers in preparation, which can't be
  declined ("Offered on date missing").

### Questions (decisions)

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
- Duplicate group titles: enforce in `GroupForm` too?
- Merging organizations drops the groups of the deleted one.
- Archiving unused contacts: deals count by creation, projects by closing.
- Reassign suggestions prefer the own project over a newer own deal.
- Non-admins may edit and delete others' non-sickness absences.
- Applying down payments when creating invoices through the API isn't
  possible yet.
