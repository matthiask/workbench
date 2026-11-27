# 11 Campaigns

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`projects_campaign_create`, `_update`, `_delete` → `CampaignForm`,
`CampaignDeleteForm`. `GET /api/campaigns/` exists.

## API

`POST /api/campaigns/`, `PATCH`/`DELETE /api/campaigns/{id}/`.

## `wb`

`wb campaigns create|update|delete`.

## Done (2026-11-27)

- `POST /api/campaigns/` (`title`, `customer`, `description`, `owned_by`
  defaulting to the current user), `PATCH /api/campaigns/{id}/` through
  `patch_with_form()`, `DELETE /api/campaigns/{id}/` through
  `delete_with_form()` with `CampaignDeleteForm`. The delete form asks no
  question, it only warns `release-projects` when the campaign has projects
  (they stay and lose it), so there's no extra parameter:
  `ignore_warnings=release-projects`.
- All three require the campaigns feature like `GET /api/campaigns/`. The
  web views don't check it themselves.
- IDs only: campaigns have no code which `by_id_or_code()` understands.
- `CampaignForm` reads `?copy=` and `?customer=` of the web interface, the
  endpoints pass it `without_query(request)`. No form changes.
- `wb campaigns create --customer ID --title TEXT [--description]
  [--owned-by]`, `wb campaigns update ID [--customer] [--title]
  [--description] [--owned-by]`, `wb campaigns delete ID`, all with
  `--ignore-warning`, `--dry-run`, `--json`. Projects join a campaign with
  `wb projects update --campaign` (package 07).
