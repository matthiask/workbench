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

## Done (2026-11-27)

- `PATCH /api/invoices/{id}/` and `DELETE /api/invoices/{id}/` take an ID
  or a code like `GET`. `down_payments` maps to the form's
  `apply_down_payment` (replaces the current ones), `tax_rate` is rounded
  to the choices' two places. `type` can't be patched (always disabled).
- `wb invoices update ID` (all form fields, `--down-payment` /
  `--no-down-payments`, `--vat/--no-vat`, `--show-/--hide-service-details`)
  and `wb invoices delete ID`. No `wb invoices settle`:
  `update --status paid --closed-on --payment-notice` does it, and the
  settle URL counts as covered by the PATCH route.
- Different from the spec: the field restrictions only apply to
  **freezed** invoices (on or before the freeze date, or archived). Sent
  invoices after the freeze date keep all fields, changing anything but
  status, closed on, payment notice and third party costs warns
  (`maybe-unintentional-invoice-change`), amounts too.
- Two changes to `patch_with_form()` for every package: fields which the
  form disables or leaves out (e.g. amounts of freezed invoices, the
  discount of credits) are refused ("This field cannot be changed.")
  unless the value is empty, instead of being ignored silently; and the
  ignored warnings are passed to the form like the web interface's
  checkbox, because forms act on them (`should_ignore_warnings()`:
  reopening a paid invoice clears its closing date).
