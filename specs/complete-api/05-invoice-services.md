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
