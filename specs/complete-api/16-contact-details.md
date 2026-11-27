# 16 Contacts: change and remove details

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`PersonForm` with its formsets for email addresses, phone numbers and
postal addresses. The API adds details (`POST .../people/{id}/details/`)
and changes postal addresses (`PATCH .../postal-addresses/{id}/`), but
can't change or remove email addresses and phone numbers, or remove
postal addresses.

## API

`PATCH`/`DELETE /api/contacts/people/{id}/email-addresses/{id}/`,
`.../phone-numbers/{id}/`, `DELETE .../postal-addresses/{id}/`. Show the
detail IDs in `GET /api/contacts/people/{id}/` if they're missing.

## `wb`

`wb people change-email|remove-email|change-phone|remove-phone|
remove-address` or one `wb people details update|remove` command,
whichever fits the existing `add-details` / `change-address` better.
