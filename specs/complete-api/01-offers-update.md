# 01 Offers: update and status

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Goal

`PATCH /api/offers/{id}/` takes every field of `OfferForm`, for offers in
any status, with the form's rules. Today it only accepts a few fields of
offers in preparation and service groups (`owned_by` since wb 0.56.0).

## Web reference

`offers_offer_update` → `OfferForm` (`workbench/offers/forms.py`):
`offered_on`, `valid_until`, `closed_on`, `title`, `description`,
`owned_by`, `status`, `postal_address`, `discount`, `liable_to_vat`,
`tax_rate`, `show_service_details`, `work_completed_on`,
`is_budget_retainer`, `external_reference`; `delete_planned_work` when
declining or discarding an offer with future planned work. Services stay
unchangeable once sent (`services_changeable`), which the services
endpoints already respect.

## API

- `PATCH /api/offers/{id}/` through `patch_with_form()`. `status` as an
  `offer_status` key. Keep the special case for external references only
  (it must keep working for accepted offers). Remove the 409 for offers
  not in preparation; the form decides.
- Linked deals: closing a deal settles its offers; changing an offer's
  status doesn't touch deals. Check `DealForm` / signals for surprises.

## `wb`

`wb offers update` gets `--status`, `--offered-on`, `--valid-until`,
`--closed-on`, `--work-completed-on`, `--postal-address`,
`--liable-to-vat/--not-liable-to-vat`, `--tax-rate`,
`--show-service-details/--hide-service-details`, `--budget-retainer/
--no-budget-retainer`, `--delete-planned-work/--keep-planned-work`,
`--ignore-warning`.

## Tests

Sent offer: owner and status change, services refused. Declining with
future planned work asks (error with code) and deletes with
`delete_planned_work`. Accepted offer back into preparation: warning
`status-change-but-already-closed` unless ignored.

## Putting offers back into preparation

Decided: wanted, it's the defined workflow for changing an offer which
has been sent or accepted (put it back into preparation, change it, send
it again). `wb offers update ID --status in_preparation` must work for
sent and accepted offers; the form's warning
(`status-change-but-already-closed`) stays and is ignored by code. Mention
the workflow in `wb offers update --help`, `cli/README.md` and the
`workbench-offer` skill (revising an offer that isn't in preparation
anymore).

## Done (2026-11-27)

What differs from the spec, and what later packages need to know:

- `OfferForm(with_items=False)` leaves services and headings alone: the
  formsets stay unbound, aren't validated and aren't saved. The API changes
  them through `wb services` and `wb offers headings` only.
- `OfferForm.is_valid()` takes `ignore_warnings` like the base form, and
  the planned work question also appears when the status is posted as a
  number (the API posts numbers, the web interface strings).
- `discount: null` still removes the discount (sent as 0). `tax_rate` is a
  number like 8.1, quantized to the form's choices. Booleans set to null
  are false.
- Service groups lost their own 409 too: they take every field of the
  form, like in the web interface.
- Changing only `external_reference` still skips the form, so it never
  warns. Any other change goes through the form; `short-postal-address`
  only warns when the postal address is new or changed (decided
  2026-11-27), so old offers with short addresses change without ignoring
  it.
- Linked deals: no signals; changing an offer's status doesn't touch its
  deals. Only closing a deal (`DealForm`) accepts or declines its offers.
  An accepted offer put back into preparation stays linked to its
  (possibly closed) deal.
- Dates of `wb offers update` take `""` to empty them (`--work-completed-on
  ""` resumes logging).
