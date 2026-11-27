# 02 Offers: copy, delete, renumber

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

- `offers_offer_copy` → `copy_offer` with `OfferCopyForm` (target
  project).
- `offers_offer_delete` → `OfferDeleteView` with `OfferDeleteForm`.
- Renumbering a project's offers → `OffersRenumberForm`
  (`workbench/projects/views.py`).

## API

- `POST /api/offers/{id}/copy/` `{project}` → the new offer.
- `DELETE /api/offers/{id}/` through `delete_with_form()`.
- `POST /api/projects/{id}/offers/renumber/` with the form's fields.

## `wb`

`wb offers copy ID --project P`, `wb offers delete ID`,
`wb projects renumber-offers P`.

## Questions

- Is renumbering worth an endpoint, or rare enough for the browser?
