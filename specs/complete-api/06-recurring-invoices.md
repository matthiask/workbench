# 06 Recurring invoices

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`invoices_recurringinvoice_create`, `_update`, `_delete` →
`RecurringInvoiceForm` (`workbench/invoices/recurring_urls.py`). The
existing `PATCH /api/recurring-invoices/{id}/` only takes title,
description, owner and the mail settings.

## API

- `POST /api/recurring-invoices/` and the PATCH extended to all form
  fields through `patch_with_form()` (`next_period_starts_on` is disabled
  once invoices exist; the form decides). `site` with the hosting feature.
- `DELETE /api/recurring-invoices/{id}/`.

## `wb`

`wb recurring-invoices create|delete`, more options on `update`.
