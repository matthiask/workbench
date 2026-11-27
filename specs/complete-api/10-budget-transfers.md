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
