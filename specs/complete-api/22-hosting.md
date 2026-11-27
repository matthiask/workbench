# 22 Hosting: delete, contact roles

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`hosting_site_delete`, `hosting_server_delete`,
`hosting_sitecontact_update` (`SiteContactForm`, the role). Adding and
removing site contacts and archiving sites and servers are in the API.

## API

`DELETE /api/hosting/sites/{id}/`, `.../servers/{id}/`, `PATCH
/api/hosting/sites/{id}/contacts/{contact_id}/` (role).

## `wb`

`wb sites delete`, `wb servers delete`, `wb sites contacts update`.
