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
