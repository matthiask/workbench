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
