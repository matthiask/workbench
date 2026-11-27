# 08 Services: move to another project

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`projects_service_move` → `ServiceMoveForm` (`workbench/projects/forms.py`).
Merging, reassigning the logbook, reordering and the service type are in
the API already.

## API

`POST /api/services/{id}/move/` `{project}`; invoiced services stay where
they are (the form refuses).

## `wb`

`wb services move ID --project P`.

## Done (2026-11-27)

- `POST /api/services/{id}/move/` `{project}` (ID or code), `dry_run`,
  `ignore_warnings`; returns the moved service (`ServiceOut`). Goes
  through `patch_with_form()` with `ServiceMoveForm.__wrapped__` (the form
  is decorated with `add_prefix("modal")`). No form changes, the web
  interface is unchanged.
- Like the web interface: closed projects, invoiced services and services
  with invoiced (archived) entries are the form's errors at `project`; a
  flat rate of the new project is the warning `new-project-has-flat-rate`
  and applied to the service. Unknown projects are an error at `project`.
- Services bound to an offer: the web form only shows a message when it
  is opened (GET) and refuses the POST through the model's validation
  ("The offer must belong to the same project as the service."), which the
  API returns at `["body", "data"]`. Detach the service from its offer
  first (`wb services update ID --clear-offer`, for offers in preparation).
- Like the merge and reassign endpoints, no feature is required (the web
  view isn't controlling-only either, only its menu entry is).
- `wb services move ID --project P` with `--dry-run`, `--ignore-warning`,
  `--json`.
