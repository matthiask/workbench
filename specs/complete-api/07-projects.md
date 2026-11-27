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
