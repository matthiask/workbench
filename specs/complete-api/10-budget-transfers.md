# 10 Budget transfers

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`projects_project_createbudgettransfer`, `projects_budgettransfer_update`,
`_delete`, `_detail` → `BudgetTransferForm`.

## API

`GET`/`POST /api/projects/{id}/budget-transfers/`,
`GET`/`PATCH`/`DELETE /api/budget-transfers/{id}/`. Check how budget
transfers enter `docs/metrics.md` and show them in `GET
/api/projects/{id}/` if they change its figures.

## `wb`

`wb projects budget-transfers list|create|update|delete`.

## Done (2026-11-27)

- `GET`/`POST /api/projects/{id}/budget-transfers/` (project by ID or
  code; the list has the transfers from and to the project, newest
  first), `GET`/`PATCH`/`DELETE /api/budget-transfers/{id}/`. All require
  the controlling feature like the web views. Writes go through
  `BudgetTransferForm.__wrapped__` with `patch_with_form()`, also for
  creating (an unsaved transfer of the source project), with `dry_run`
  and `ignore_warnings` (`budget-transfer-too-large`,
  `budget-transfer-beyond-offers`). Fields: `title`, `amount`,
  `to_project` (ID or code, null only reserves), `notes`. The source
  project can't be changed (the form doesn't have it; unknown field).
  Like the form, any project can be the target, also closed ones (only
  the web interface's autocomplete offers open projects). No delete form,
  `allow_delete()` decides. New transfers have no ID and URL with
  `dry_run`.
- Transfers change the figures (sold in the budget statistics, gross
  margin in squeeze and the profitability), so `GET /api/projects/{id}/`
  (and PATCH/DELETE, which return the same) got `budget_transfers` and
  `budget_adjustment` (net in minus out, `BudgetTransfer.objects
  .adjustments()`), both null without the controlling feature. Nothing is
  computed differently. Note: the web interface's project page shows the
  transfers to everyone, the API only with controlling, like the views.
- `wb projects budget-transfers list PROJECT`, `create PROJECT --title
  --amount [--to-project --notes]`, `update ID [--title --amount
  --to-project --notes --reserve]`, `delete ID`, with `--dry-run`,
  `--ignore-warning` (not for delete), `--json`. `wb projects show` shows
  the net effect and a table of the transfers. The controlling skill
  explains them.
- API tests are in `workbench/projects/test_budget_transfers.py` next to
  the web tests (they share its scenario). No form changes.
