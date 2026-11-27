# 03 Invoices: update and delete

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Goal

Today invoices can only be created; changing the owner of invoices
(handover, November 2026) needed the browser.

## Web reference

- `invoices_invoice_update` → `InvoiceForm`. For invoices in preparation
  most fields; for sent ones only `contact`, `customer`, `title`,
  `description`, `owned_by`, `postal_address`, `type`,
  `third_party_costs`, `status` (sent, paid, cancelled), `closed_on`,
  `payment_notice`; the freeze date and status transitions warn
  (`_is_status_unexpected()`).
- Settling (`SettleInvoiceForm`): status, closed on, payment notice; the
  invoice form covers it too.
- `invoices_invoice_delete` → `InvoiceDeleteForm`.

## API

- `PATCH /api/invoices/{id}/` through `patch_with_form()`; `status` as an
  `invoice_status` key.
- `DELETE /api/invoices/{id}/` through `delete_with_form()`.
- Setting the status to sent only records it, like in the form; nothing
  is mailed.

## `wb`

`wb invoices update ID` with options for the form's fields
(`--owned-by`, `--title`, `--description`, `--status`, `--closed-on`,
`--payment-notice`, `--invoiced-on`, `--due-on`, `--discount`, ...),
`wb invoices delete ID`. A shortcut `wb invoices settle ID --paid|
--cancelled [--closed-on] [--payment-notice]` is optional.

## Tests

Sent invoice: owner, title, status paid with closed on; amounts refused.
Invoice dated before the freeze date: the form's error. Changing the
status to sent sends no mail. Deleting a sent invoice: refused like in
the web interface.
