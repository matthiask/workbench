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

## Done (2026-11-27)

- `POST /api/offers/{id}/copy/` `{project}` (offer and project by ID or
  code), `dry_run`, `ignore_warnings`: `OfferCopyForm` unchanged (without
  its `modal` prefix), closed or unknown projects are the form's error at
  `project`, the own project is the warning `same-project`. The copy
  belongs to the caller like in the web interface; no `owned_by`.
- `DELETE /api/offers/{id}/` (ID or code) with the delete form's questions
  as query parameters `delete_services` and `delete_planned_work`, plus
  `dry_run`. The form has no warnings, so no `ignore_warnings`. Sent and
  accepted offers are refused by `allow_delete()`. Planned work blocks
  deleting (its FK protects) unless `delete_planned_work`. The form only
  offers `delete_services` when the services can go (nothing logged or
  invoiced); asking for it anyway is an error instead of being ignored.
- `form_errors()` (`tools/api.py`) locates fields mapped to a location
  starting with `"query"` there instead of below `["body", "data"]`, for
  questions of delete forms; `format_error()` in `wb` shows the parameter.
- Renumbering is trivial with the form, so it got an endpoint:
  `POST /api/projects/{id}/offers/renumber/` `{codes: {offer ID or code:
  number}}`, the other offers keep their numbers; returns the project's
  offers ordered by number. It lives in the offers router (like the other
  `/projects/{id}/offers/` routes, controlling feature), not in
  `projects/api.py`.
- Different from the spec: the command is `wb offers renumber PROJECT_ID
  OFFER=NUMBER ...`, next to the other offer commands, not `wb projects
  renumber-offers`.
- No form changes; the web interface behaves as before.
