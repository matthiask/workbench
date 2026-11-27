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

Today `PATCH /api/logbook/hours/{id}/` accepts `service` only within the
same project.

## API

- `PATCH` with a `service` of another project goes through the move form
  (keep the same-project path as it is).
- `POST /api/projects/{id}/logbook/move/` `{kind: hours|costs, entries,
  service}` through `LogbookBatchForm`.

## `wb`

`wb hours update ID --service S` (works across projects),
`wb hours move --project P --entry ... --service S`, same for costs.
