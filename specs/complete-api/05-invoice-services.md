# 05 Invoices: services

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`invoices_invoice_createservice`, `invoices_service_update`,
`invoices_service_delete` → `ServiceForm` in `workbench/invoices/forms.py`
(services of services invoices, only while in preparation).

## API

`POST /api/invoices/{id}/services/`, `PATCH`/`DELETE
/api/invoices/services/{id}/` (check the path conventions of
`/api/services/`, which are project services).

## `wb`

`wb invoices services create|update|delete`.

## Done (2026-11-27)

- `POST /api/invoices/{invoice_id}/services/` (invoice by ID or code),
  `PATCH`/`DELETE /api/invoices/services/{service_id}/`, all with
  `dry_run`. `/api/services/` are the project services; the invoice's
  services are nested below `/api/invoices/` like in the web interface's
  URLs, `services` can't be mistaken for an invoice code there.
- Create and change go through the invoices' `ServiceForm` with
  `patch_with_form()` (creating with an unsaved `Service` of the invoice,
  like package 13): `title`, `description`, `effort_type`, `effort_hours`,
  `effort_rate`, `cost`, `third_party_costs` (named like the fields of
  `GET /api/invoices/{id}/`), and `service_type` (title) which fills in the
  effort type and rate unless given, like the form's JavaScript and
  `/api/services/`. The form refuses invoices which aren't in preparation
  anymore (at `["body", "data"]`), the model the incomplete effort fields.
  `ServiceForm` has no warnings, so no `ignore_warnings`.
- Responses are the service (as in `GET /api/invoices/{id}/`) with the
  invoice and its new total (`invoice`); deleting adds `warnings`, the
  consequences the web interface shows as messages (`delete_warnings`,
  the service period now covered by the logged hours and costs).
  Deleting releases the logged hours and costs without a warning, like the
  web interface (only deleting whole invoices warns).
- Deviation: services can only be added to services invoices (error at
  `["path", "invoice_id"]`). The web URL takes any invoice, but the web
  interface links nowhere to it and only shows services of services
  invoices; others ignore them in their total.
- `wb invoices services create INVOICE --title ... [--description
  --service-type --effort-type --effort-hours --effort-rate --cost
  --third-party-costs]`, `update SERVICE_ID [same options, --clear-effort,
  --clear-cost]`, `delete SERVICE_ID`, with `--dry-run` and `--json`;
  `delete` prints the warnings. `wb invoices show` lists the service IDs.
  No form changes, the web interface is unchanged.
