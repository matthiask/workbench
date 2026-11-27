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

## Done (2026-11-27)

- `PATCH /api/recurring-invoices/{id}/` runs through `patch_with_form()`
  and takes every field of `RecurringInvoiceForm` except
  `next_period_starts_on`: the form always disables it (not only once
  invoices exist), so it isn't in the schema and is refused as an unknown
  field. The old contract (title, description, owner, mail settings, site)
  is unchanged; `site` without the hosting feature is now refused instead
  of being ignored silently. Renewing an ended recurring invoice warns
  (`recurring-invoice-backlog`) like in the web interface.
- `POST /api/recurring-invoices/` starts like the web interface's creation
  from the customer, else from the contact's organization or the site's
  customer (the query parameter the form reads). Defaults beyond the form:
  the postal address is the first billing address (like
  `POST /api/invoices/`). Third party costs have no default (decided
  2026-11-27, they defaulted to 0 at first): they're required like in the
  web form, 0 has to be passed explicitly. A missing contact warns
  (`no-contact`).
- `DELETE /api/recurring-invoices/{id}/`: no delete form, no warnings
  (`delete_with_form()` with `allow_delete()`); the invoices created stay.
- The output has the new fields `postal_address`, `create_invoice_on_day`,
  `subtotal`, `discount`, `liable_to_vat` and `create_project`.
- `wb recurring-invoices create|update` share all options (`--customer`,
  `--contact`, `--postal-address`, `--starts-on`, `--ends-on` (`""`
  renews), `--periodicity`, `--create-invoice-on-day`, `--subtotal`,
  `--third-party-costs`, `--discount`, `--vat/--no-vat`,
  `--create-project/--no-create-project`, the mail options and `--site`),
  `wb recurring-invoices delete ID`. The `workbench-hosting` skill proposes
  creating and ending recurring invoices with `wb` (after asking).
