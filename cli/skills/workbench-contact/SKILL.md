---
name: workbench-contact
description: Add a person (and their organization) to Workbench from unstructured data such as an email signature, a business card, a web page or a pasted address, using the `wb` CLI. Use when the user wants to add, create or import a contact, person, address or organization in Workbench.
---

# Adding Workbench contacts from unstructured data

The `wb` CLI talks to Workbench (see `wb --help`). If `wb` isn't installed or
configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`, which authorizes `wb` in the browser. Writing
needs `--write`; if `wb` answers that the token only allows reading, ask the
user to log in with `--write` instead of working around it.

## 1. Look for existing records

Contacts are often in Workbench already. Search for the person, their email
address and their organization:

    wb contacts search <family name>
    wb contacts search <organization>
    wb people show <person_id>
    wb organizations show <organization_id>

- If the person exists already, compare their details with the data. New
  email addresses, phone numbers or postal addresses can be added (see
  below). Names, the salutation, the organization and the notes are changed
  with `wb people update <person_id> ... --dry-run` (see `--help`), outdated
  details removed with its `--remove-*` options and postal addresses changed
  with `wb people change-address`; confirm changes with the user first.
- If the organization exists, use its ID (`organization`). If several match,
  ask which one. Only use `new_organization` when there's none. If the data
  has a central email address (info@, kontakt@, ...) or a reception number,
  they belong to the organization, not the person: create it first with
  `wb organizations create "<name>" --email ... --phone-number ... --dry-run`
  (after the user's approval without `--dry-run`) and use its ID.

## 2. Get the schema

    wb people context > <scratchpad>/context.json

`import_schema` is the exact JSON schema of a person.

## 3. Draft the person

Write the person as YAML to the scratchpad, e.g. `<scratchpad>/person.yaml`:

```yaml
given_name: Hans
family_name: Muster
address: Herr
salutation: Lieber Hans           # or: Sehr geehrter Herr Muster
address_on_first_name_terms: true
organization: 345                  # or: new_organization: Beispiel AG
email_addresses:
  - email: hans@example.com
  - type: Home
    email: hans.muster@example.org
phone_numbers:
  - type: Mobile
    phone_number: 079 123 45 67
  - phone_number: +41 44 123 45 67
postal_addresses:
  - street: Bahnhofstrasse
    house_number: "1"
    postal_code: "8001"
    city: Zürich
```

Guidelines:

- Only use what the data says. Don't guess email addresses, phone numbers or
  genders; ask if `address` or the salutation are unclear.
- The salutation is in the language of the correspondence (usually German).
  Use first-name terms only if the data or the user says so.
- `type` of email addresses, phone numbers and postal addresses defaults to
  Work; use Mobile or Home where it's clear (other types are possible,
  but these are the ones the forms suggest).
- Quote postal codes and house numbers so they stay strings.
- Leave out `notes` unless the user wants to keep something, and never put
  sensitive information there.

## 4. Review and create

Validate it on the server and show the result to the user:

    wb people create <scratchpad>/person.yaml --dry-run

Workbench rejects people and organizations whose names exist already, and email
addresses which are in use. Show these to the user instead of working around
them. Only pass `--allow-duplicates` when the user confirms that it's really
someone (or something) else with the same name. If the person exists twice
already (e.g. under an old name), propose merging them with
`wb people merge <duplicate_id> --into <keep_id> --dry-run` and only run it
without `--dry-run` once the user confirms.

Only after the user explicitly approves:

    wb people create <scratchpad>/person.yaml

Report the person's URL so they can be checked in Workbench.

## Adding details to existing people

Write only the new details to `<scratchpad>/details.yaml`, using the
`email_addresses`, `phone_numbers` and `postal_addresses` of the schema, show
them to the user and validate them:

    wb people add-details <person_id> <scratchpad>/details.yaml --dry-run

Existing details are never changed or removed. After the user's approval:

    wb people add-details <person_id> <scratchpad>/details.yaml
