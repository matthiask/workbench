# 07 Projects: all fields, delete, projected invoices

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

- `projects_project_update` → `ProjectForm`; the existing PATCH handles
  title, description, customer, contact, type, internal type, owner,
  closed on. Missing: `flat_rate`, `campaign`, `cost_center` and whatever
  else the form has.
- `projects_project_delete` → `generic.DeleteView` (`allow_delete()`).
- Projected invoices → `ProjectedInvoicesProjectForm` (a formset of
  `ProjectedInvoiceForm`). Read-only today (`/api/projected-invoices/`).

## API

- Extend `PATCH /api/projects/{id}/` (move it onto `patch_with_form()`).
- `DELETE /api/projects/{id}/`.
- `PUT /api/projects/{id}/projected-invoices/` replacing the list (like the
  formset), with the freeze date rules of the form.

## `wb`

More options on `wb projects update`, `wb projects delete`,
`wb projected-invoices set PROJECT --invoice DATE=AMOUNT[:DESCRIPTION]...`
or from a YAML file.

## Done (2026-11-27)

- `PATCH /api/projects/{id}/` takes every field of `ProjectForm`: also
  `campaign` (ID), `cost_center` (title or ID, there's no cost center
  endpoint), `flat_rate`, `budget_alert_at` and
  `suppress_planning_update_mails`; null empties them. Fields of features
  the user doesn't have (campaigns, labor costs, controlling, planning)
  are refused like the form leaves them out. The form gets the request
  without query parameters (it reads initial values from them). The
  response is now `ProjectDetail` (with `cost_center` and `deals`);
  `ProjectOut` gained `budget_alert_at` and
  `suppress_planning_update_mails`, `flat_rate` is rounded to two places.
- `DELETE /api/projects/{id}/` (ID or code) through `delete_with_form()`;
  the default `allow_delete()` refuses projects with offers, invoices or
  logged hours and costs. No delete form, so no `ignore_warnings`.
- `PUT /api/projects/{id}/projected-invoices/` with `{projected_invoices:
  [{id?, invoiced_on, gross_margin, description}]}` builds the web formset
  (`ProjectedInvoicesProjectForm`, unchanged): listed ones are changed,
  the others deleted, the rest created. Items without `id` change an
  unlisted projected invoice with the same date, so that projections on or
  before the freeze date can be kept without knowing their IDs (the form
  only refuses new or changed dates on or before it). Requires the
  `PROJECTED_GROSS_MARGIN` feature like the web interface's links (the
  view itself isn't feature-gated). Returns the project, its projected
  invoices and their total.
- `wb projects update` (`--campaign`, `--cost-center`, `--flat-rate`,
  `--budget-alert-at`, `--suppress-/--send-planning-update-mails`, and
  `--no-contact`, `--no-campaign`, `--no-cost-center`, `--no-flat-rate`,
  `--no-budget-alert`), `wb projects delete`, `wb projected-invoices set
  PROJECT --invoice DATE=AMOUNT[:DESCRIPTION]... | --file FILE | --clear`
  (the command is defined in `cli/wb/projects.py` on the group of
  `cli/wb/invoices.py`).
