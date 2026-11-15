---
name: workbench-mailing-list
description: Maintain a group of people in Workbench for a mailing (e.g. Christmas cards, gifts, invitations, a newsletter) with the `wb` CLI, update it from an old spreadsheet and from recent projects and deals, and export it. Use when the user wants to prepare, update or clean up a mailing list, find who is missing or who left, or import a list of recipients into a Workbench group.
---

# Maintaining a mailing list in Workbench

A mailing list is a group of people in Workbench. Workbench is the source of
truth: the list for the mailing is an export of the group, not a separate
spreadsheet. The people list in the web interface exports a group as XLSX
with the postal addresses (Contacts → People → filter by group → export).

The `wb` CLI talks to Workbench (see `wb --help`). If `wb` isn't installed or
configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`. Writing needs `--write`; if `wb` answers that the
token only allows reading, ask the user to log in with `--write` instead of
working around it.

Propose, people decide. Never overwrite what's in Workbench: add missing
data, and show differences to the user. Validate every change with
`--dry-run` and only write after the user explicitly approves.

## 1. The group

    wb groups
    wb groups search --include-archived

Find the group of the mailing. If there's none, ask for the title and create
it after the user's approval:

    wb groups create "Christmas mailing" --dry-run

Groups of earlier, different mailings (e.g. a yearly group which isn't used
anymore) are archived only when the user says so:

    wb groups update <group_id> --archive

People who are only in archived groups are archived automatically after five
years without use, so don't archive groups whose people should be kept
without asking.

## 2. Look at the current members

    wb people search --group "<group>" --include-archived --csv

`--include-archived` includes archived people: they usually left their organization. For
each of them, look at the organization (`wb organizations show <id>`) and
propose who could receive the mailing instead; ask the user.

Members are listed with their primary contact (the person in the user's
company who knows them) and their postal address. Point out members without
a postal address and members whose primary contact isn't active anymore
(`wb users search --include-inactive`).

## 3. Find who is missing

People who should probably be on the list:

    wb people search --projects-or-deals-since <date> --csv
    wb people search --without-groups --csv

The first lists the contacts of projects and deals created since the date
(ask how far back, e.g. two to five years), the second people who aren't in
any active group yet, i.e. nobody decided about them. Leave out members of
the group and archived people.

Present the candidates grouped by their primary contact, so that everyone can
decide about the people they know. For each candidate show the organization
and the latest project or deal (`wb projects search --include-closed --json` has the
contact, the customer, the project lead and the creation date).

## 4. Import an old list (once)

If the user has a spreadsheet of an earlier mailing, match each row with
Workbench (`wb people search <name> --include-archived --json`, compare the organization)
and sort the rows into: found, found but archived (left), several matches,
duplicates in Workbench (the same person twice at the same organization),
missing. Don't guess on several matches; ask.

- Found people who should get the mailing go into the group.
- Missing people are created with the conventions of the workbench-contact
  skill (`wb people context`, `wb people create --dry-run`), linked to the
  existing organization if there is one.
- Postal addresses are only added to people without one
  (`wb people add-details`); different addresses are shown, not changed.
- Duplicates are merged after the user confirms which one to keep (usually
  the one with projects, deals or the current name, e.g. after a marriage):
  `wb people merge <duplicate_id> --into <keep_id> --dry-run`. Details,
  groups and projects move, name and organization stay those of the person
  kept.
- The primary contact is only set where the current one isn't active anymore.
  Take the responsible person from the list if they're active, otherwise
  propose the lead of the person's latest project (as its contact, else of
  their organization). Ask about the rest.

Show the result as a table (or a spreadsheet for many people) before changing
anything.

## 5. Apply

After the user's approval, person by person, each first with `--dry-run`:

    wb people update <person_id> --add-group "<group>" --dry-run
    wb people update <person_id> --primary-contact <short name> --dry-run
    wb people update <person_id> --remove-group "<group>" --dry-run

Groups which apply to organizations (e.g. industries) are added to the
person's organization, like in the web interface; mailing groups usually
don't. Only archive people (`--archive`) when the user confirms they left.

## 6. Export

The export for the mailing is the people list of the web interface filtered
by the group (XLSX with postal addresses). For a check in the terminal:

    wb people search --group "<group>" --csv

Report how many people the group has, how many have no postal address and
what is still open.
