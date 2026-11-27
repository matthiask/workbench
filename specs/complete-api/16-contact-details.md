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

## Done (2026-11-27)

- `PATCH`/`DELETE /api/contacts/people/{id}/email-addresses/{id}/` and
  `.../phone-numbers/{id}/` (`type`, `email` / `phone_number`),
  `DELETE .../postal-addresses/{id}/`, all with `dry_run`; they return the
  person like `GET /api/contacts/people/{id}/`, which listed the detail
  IDs already. A detail of another person is a 404.
- Changes go through the forms of the person form's formsets
  (`EmailAddressFormset.form`, `PhoneNumberFormset.form`,
  `PostalAddressForm`) with the detail's current values (`form_data()`)
  and the given fields on top, so phone numbers are normalized and types
  keep the suggested spelling like in the web interface. The existing
  `PATCH .../postal-addresses/{id}/` uses `PostalAddressForm` now too
  instead of the model's `full_clean()` (same rules, same error
  locations). No form changes, the web interface is unchanged.
- Like the formsets, nothing else is checked, removing has no rules.
  Exception, decided 2026-11-27: changing an email address to one another
  person or an organization (centrally) uses already is a warning
  (`email-in-use`; the same rule as creating and `details/`: any other
  person, archived or not, of any organization), in the person form
  (changed and added addresses) and in `PATCH .../email-addresses/{id}/`,
  which takes `ignore_warnings` for it (`wb people change-email
  --ignore-warning email-in-use`). Creating and `details/` keep rejecting
  them as errors. The other endpoints and commands take no
  `ignore_warnings`.
- `wb people change-email PERSON_ID EMAIL_ID [--email] [--type]`,
  `change-phone PERSON_ID PHONE_ID [--phone-number] [--type]`,
  `remove-email|remove-phone|remove-address PERSON_ID ID`, all with
  `--dry-run` and `--json`. The detail ID is an argument, not an option
  like `change-address --address ID`, because `--email` and
  `--phone-number` are the new values (options named like the API fields).
- `wb people update --remove-email/--remove-phone/--remove-postal-address`
  and the `--*-type` options stay (removing by value, several at once).
- Open: email-in-use on create/details. Decided 2026-11-27: in
  `POST /api/contacts/people/` and `POST .../people/{id}/details/`, an
  address the same person has already stays a hard error without code (on
  create only "Listed twice."); one another person or an organization uses
  becomes the ignorable warning `email-in-use` (reuse
  `email_in_use_warning()`, located at the address's field). Nothing is
  implemented yet. Left: replace `_email_errors()` in
  `workbench/contacts/api.py` accordingly, add `ignore_warnings`
  (`IGNORE_WARNINGS`) to `person_add_details`, fix the `allow_duplicates`
  description (it mentions email addresses but never applied to them) and
  the docstrings of `email_in_use_warning()`, `person_create` and
  `person_add_details`; `--ignore-warning` for `wb people add-details`
  (`wb people create` has it already), docstring of `wb people create`,
  version bump; `cli/README.md` ("email addresses which are in use are
  always rejected"), the `workbench-contact` skill (step 4: still ask the
  user before ignoring the warning); API tests for both endpoints (same
  person, another person, an organization, `ignore_warnings`, dry run) and
  a round trip in `workbench/test_cli.py`.
