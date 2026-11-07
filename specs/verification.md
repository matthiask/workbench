# Verification rounds

Open findings of the verification rounds (see `AGENTS.md`), removed when
they're fixed or decided.

## Round 1 (2026-11-07)

### Verified, need a decision

- Moving a service without offer to another project takes its invoiced
  hours along without a warning (`ServiceMoveForm`); the budget statistics
  then show accruals on the old project and work not invoiced on the new one.
- Invoicing a service from the offer after invoicing it from the logbook
  gives no warning, the work is invoiced twice (the other way round may be
  work beyond the offer).
- Entries with `hours_for_invoicing=0` are never archived when invoicing
  from the logbook if their service has nothing else to invoice (the form
  doesn't list the service), they keep the project in `old_projects()`.
- Archived hours can still change service and hours (behind the
  `part-of-invoice` warning), the invoice then disagrees with the logbook.
- Recurring invoices ignore their own `tax_rate` (commented out since
  36c89f78, the form doesn't offer it): drop the field, or make it work?
- Versions like `0.20.0rc1` parse to `()` and are "too old"
  (`workbench/cli_version.py`, `cli/wb/core.py`): only plain versions by
  convention?
- Timestamps accept closed projects (by ID) and services of closed projects
  or without logging; the logbook form rejects them later.
- `filter_users()` reports "Unknown users" for a user outside the team.
- `clear_sickness_descriptions()` misses the history of absences whose
  description was cleared or reason changed (bounded by `prune_audit`).
- Closing a deal preselects linked offers in preparation and service groups,
  which fail validation ("Offered on date missing") when accepting or
  declining; declining unsent offers could discard them instead.

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
