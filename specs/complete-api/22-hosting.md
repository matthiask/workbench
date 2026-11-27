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

## Done (2026-11-27)

- `DELETE /api/hosting/sites/{id}/` and `DELETE
  /api/hosting/servers/{id}/` take an ID or a title like `GET` and go
  through `delete_with_form()` (the views have no delete form, the model's
  `allow_delete()` decides). They return what was deleted, the site with
  its recurring invoices (with the controlling feature).
- Like the web interface: a server with sites, also archived ones, is
  refused (`PROTECT`, "Cannot delete ... because of related objects");
  deleting a site deletes its contacts (`CASCADE`) and leaves its
  recurring invoices without site (`SET_NULL`), without warning, like the
  web interface.
- `PATCH /api/hosting/sites/{id}/contacts/{contact_id}/` takes `role` and,
  because the form has it too, `person`. `contact_id` is the site
  contact's ID (`contacts[].contact_id`) and must belong to the site (404
  otherwise). Goes through `patch_with_form()` with
  `SiteContactForm.__wrapped__`: `@add_prefix("modal")` wraps the class in
  a function, the unwrapped class has no prefix. No form change.
- `wb sites delete SITE`, `wb servers delete SERVER` (`--dry-run`,
  `--json`), `wb sites contacts update SITE CONTACT_ID --role
  outage|it [--person ID]`; `wb sites show` lists the contact IDs in its
  own column. No `--ignore-warning`: the hosting forms have no warnings.
- The `workbench-hosting` skill mentions changing roles and deleting
  duplicates (archiving stays the rule for sites which ran).
