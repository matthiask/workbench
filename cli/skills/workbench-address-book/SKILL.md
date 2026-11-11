---
name: workbench-address-book
description: Clean up the Workbench address book with the `wb` CLI. Merges duplicate people and organizations, reassigns people of users who left, moves generic email addresses (info@, kontakt@, ...) and reception phone numbers from people to their organization, fixes outdated postal addresses and archives organizations nobody works at anymore. Use when the user wants to clean up, tidy, deduplicate or check contacts, people, organizations or addresses in Workbench.
---

# Cleaning up the Workbench address book

The `wb` CLI talks to Workbench (see `wb --help`). If `wb` isn't installed or
configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`. Writing needs `--write`; if `wb` answers that the
token only allows reading, ask the user to log in with `--write` instead of
working around it.

Propose, people decide. Look first, then show the user what you'd change,
grouped so they can decide quickly (a table per step, or a spreadsheet for
many rows). Validate every change with `--dry-run` and only write after the
user explicitly approves. Merging deletes the duplicate and can't be undone;
never merge, archive or remove anything on a guess.

Ask what to clean up: the whole address book or one step, everything or
only the contacts of one primary contact (`--primary-contact`) or one
organization. Address books have hundreds of findings: work in batches
(`--limit`, `--offset`) and report what's still open when stopping.

Take the type of email addresses, phone numbers and postal addresses into
account (`wb people show` lists it, e.g. `Email (Work)`, `Address (Home, ID
123)`). Work, Mobile and Home are the usual types, others are free
text:

- Types starting with `organization` (e.g. `organization Work`) were copied
  from the organization by an old import. When several people share an
  address or a number, the one who has it with their own type (without the
  prefix) is usually its owner, the others have a copy.
- Private addresses (Home, Privat, Zuhause) are supposed to differ from the
  organization's, and other special types (e.g. Rechnungen, Büro Lausanne)
  may be deliberate; leave them alone or ask.
- A private address saved as a work address gets the right type instead of
  being removed or changed:

      wb people update <person_id> --postal-address-type <address_id> Home --dry-run

## 1. Duplicates

    wb people duplicates
    wb people show <person_id>
    wb organizations show <organization_id>

Groups of people with the same name, or the same email address and a common
given or family name. The first person of a group is usually the oldest
active one. People with the same name may be different people (common
names, father and son): compare organizations, email addresses and phone
numbers, and ask when it isn't obvious.

Propose which person to keep: the one with projects, deals or invoices
(`wb projects search --include-closed --json` has the contacts), the one
linked to a user, the one at the current organization, the one with the
current name (e.g. after a marriage). Then:

    wb people merge <duplicate_id> --into <keep_id> --dry-run

Projects, deals, invoices, details and groups move; name and organization
stay those of the person kept; an inactive primary contact is replaced by
the duplicate's active one. If the duplicate is the contact of projects or
deals and the person kept belongs to another organization, Workbench warns
(`other-organization`); only pass `--ignore-warning other-organization`
after the user confirms.

Duplicate organizations show up as the same person at two organizations
with similar names, or when searching (`wb organizations search <name>
--include-archived`). Keep the one with projects and invoices, usually the
older one:

    wb organizations merge <duplicate_id> --into <keep_id> --dry-run

People, projects, deals, invoices and groups move; missing email and billing
addresses are taken over. Duplicate people of the merged organizations show
up in `wb people duplicates` afterwards.

## 2. People of users who left

    wb users search --include-inactive
    wb people reassign-suggestions
    wb people reassign-suggestions --from <short name> --csv

Every person has a primary contact, the user who knows them. For people of
inactive users Workbench suggests the lead of the latest project or the
owner of the latest deal. Show the suggestions grouped by the new primary
contact and apply them after the user's approval:

    wb people reassign --from <short name> --suggested --dry-run
    wb people update <person_id> --primary-contact <short name> --dry-run

People without a suggestion stay with the inactive user unless the user
names someone; they are often candidates for archiving (step 5).
Organizations have primary contacts too:

    wb organizations search --primary-contact <short name>
    wb organizations update <organization_id> --primary-contact <short name> --dry-run

## 3. Generic email addresses and phone numbers

    wb people shared-emails

Lists addresses which several active people of the same organization have,
and central addresses of organizations which are still on people. Sort them:

- Generic addresses (info@, kontakt@, contact@, office@, hello@, mail@,
  sekretariat@, empfang@) belong to the organization: set them as its
  central address if it has none, then remove them from the people. The
  central address is shown on every person of the organization.

      wb organizations update <organization_id> --email info@example.com --dry-run
      wb people update <person_id> --remove-email info@example.com --dry-run

- Addresses for invoices (buchhaltung@, rechnungen@, kreditoren@,
  accounting@, invoices@) become the accounts payable address
  (`--accounts-payable-email`), which payment reminders suggest first.
- If the organization has a different central address already, ask.
- A personal address on several people is usually a duplicate (step 1),
  or a couple or family; ask.

Phone numbers work the same way: the reception's number belongs to the
organization (its central number, shown on every person), mobile numbers
on several people are usually duplicates or mistakes; ask.

    wb people shared-phones
    wb organizations update <organization_id> --phone-number "+41 44 123 45 67" --dry-run
    wb people update <person_id> --remove-phone "+41 44 123 45 67" --dry-run

## 4. Postal addresses

    wb organizations search --several-postal-addresses
    wb organizations show <organization_id>

Organizations whose active people have different addresses; `show` lists
each address with its ID and the people who have it. The address most
people have is usually the current one, but not always: ask the user, or
look at the organization's website if they agree. Private addresses don't
count as different addresses, but `show` lists every address of the active
people without its type: check `wb people show` before changing one. When a
person has two work addresses, one is often private (fix its type, see
above) or old. Then change the old address for the people who still have
it:

    wb organizations change-address <organization_id> --address <address_id> \
        --street "Neuweg" --house-number 2 --postal-code 8001 --city Zürich --dry-run

Fields which aren't given stay; `--person ID` (repeated) limits the change
to some people. People without a complete address:

    wb people search --missing-postal-address --organization <organization_id>

get their organization's current address after the user agrees, with `wb
people add-details` (see the workbench-contact skill for the format). Never
change addresses you only guessed.

## 5. Archiving

    wb organizations search --without-active-people

Organizations whose people are all archived (or which never had any).
Propose archiving those without recent projects, deals or invoices; ask about
the rest:

    wb organizations update <organization_id> --archive --dry-run

People who left an organization but are still worth keeping (e.g. former
employees) aren't archived: move them to their new organization, or to none
if it isn't known, and remove the old organization's email and postal
addresses. Projects, deals and invoices keep them as their contact; moving
the contact of any warns (`organization-update`), pass `--ignore-warning
organization-update` after the user confirms. Membership in an active group
(e.g. the former team) keeps them from being archived automatically:

    wb people update <person_id> --organization <organization_id> --dry-run
    wb people update <person_id> --organization "" --dry-run
    wb people update <person_id> --remove-postal-address <address_id> --dry-run

`wb people show` lists the IDs of the postal addresses.

People are only archived when the user confirms we lost touch with them (`wb
people update <person_id> --archive`); archiving the last active person of an organization
without open projects or deals archives the organization too. Workbench
archives contacts unused for five years on its own, so old contacts don't
need to be archived by hand.

## Report

Summarize what changed (merged, reassigned, addresses moved or changed,
archived) and what is still open, with the commands to continue.
