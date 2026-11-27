# 09 Logbook: move entries

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

- `logbook_loggedhours_move`, `logbook_loggedcost_move` →
  `LoggedHoursMoveForm` / `LoggedCostMoveForm`: any logging service of an
  open project; archived entries and closed projects refused.
- Batch: `projects_project_logbook_batch_update_hours|costs` →
  `LogbookBatchForm` (`workbench/projects/views.py`
  `logbook_batch_update`).

## API

- `PATCH` with a `service` of another project goes through the move form
  (keep the same-project path as it is).
- `POST /api/projects/{id}/logbook/move/` `{kind: hours|costs, entries,
  service}` through `LogbookBatchForm`.

## `wb`

`wb hours update ID --service S` (works across projects),
`wb hours move --project P --entry ... --service S`, same for costs.

## Done (2026-11-27)

- `PATCH /api/logbook/hours|costs/{id}/` with a `service` of another
  project goes through `LoggedHoursMoveForm` / `LoggedCostMoveForm`
  (any logging service of an open project; archived entries and closed
  projects refused with the form's messages). The same-project path is
  unchanged. Other fields given together with the move are changed
  afterwards with the logbook form on the new project, in the same
  transaction: their errors and warnings roll back the move too. A pure
  move runs only the move form, so it has no warnings (like the web
  interface). Invoiced but not yet archived entries move like in the
  web interface (the move form only checks `archived_at`).
- `POST /api/projects/{project_id}/logbook/move/` `{kind, entries,
  service}` through `LogbookBatchForm` unchanged, with `dry_run` and
  `ignore_warnings` (the form has none). Like the web view: only entries
  of the project which aren't archived are choices (others are the form's
  "Select a valid choice" at `entries`), only services of the same project
  (the batch form doesn't move across projects; loop over `PATCH` for
  that), closed projects refused at `["path", "project_id"]`. `service`
  is required in the API (moving is the only thing the form does).
  Returns the moved entries (`list[LoggedHoursOut] | list[LoggedCostOut]`,
  by `kind`).
- `wb hours|costs update ID --service S` works across projects;
  `wb hours|costs move --project P --entry ID ... --service S` with
  `--dry-run`, `--ignore-warning`, `--json`. No form changes.
