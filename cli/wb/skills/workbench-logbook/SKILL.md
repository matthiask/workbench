---
name: workbench-logbook
description: Log hours, costs and breaks in Workbench with the `wb` CLI, e.g. from notes, a calendar, commits or timestamps, and correct or delete logged entries. Use when the user wants to log, book, record, fix, move or delete hours, time, expenses, costs or breaks in Workbench, or asks what they logged.
---

# Logging hours and costs in Workbench

The `wb` CLI talks to Workbench (see `wb --help`). If `wb` isn't installed or
configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`, which authorizes `wb` in the browser. Writing
needs `--write`; if `wb` answers that the token only allows reading, ask the
user to log in with `--write` instead of working around it. Use `wb`, not
the web interface in a browser: `wb` shows each warning with its code.

## 1. What has been done, what is logged already

- The user's notes, calendar, commits or whatever they point you to.
- `wb timestamps list` shows today's timestamps, logged hours and breaks
  (the notes of timestamps are what the user said they were doing).
- `wb hours` lists the user's hours of this week, `wb hours search
  --period this-month --rendered-by <short name>` more. Don't log work twice.

Only use what the sources say. Ask about gaps and unclear durations instead
of filling a day up to its target hours.

## 2. Find the services

    wb projects search <words>
    wb services search --project <project_id>

Hours and costs are logged on a service of an open project which allows
logging ("no logging" marks the others). Prefer the service the user logged
on before for the same kind of work (`wb hours search --project ID`). If no
service fits, ask; new services are created with `wb services create` (see
the `workbench-offer` skill for good titles), not invented.

## 3. Propose, then log

Show a table: date, project, service (with ID), hours, description. Hours in
tenths (0.1h = 6 minutes), rounded up. Descriptions are specific and
understandable for the customer, they may end up on an invoice. Wait for the
user's approval, then validate each entry first:

    wb hours create <service_id> <hours> "<description>" --rendered-on YYYY-MM-DD --dry-run
    wb hours create <service_id> <hours> "<description>" --rendered-on YYYY-MM-DD

`--rendered-by <short name>` logs hours of someone else (reported to
personnel administration), `--hours-for-invoicing` values the work with
other hours than the time spent, only when the user says so.

Costs (excl. tax; third party costs incl. tax, what was paid):

    wb costs create <service_id> <cost> "<description>" --third-party-costs <paid> --dry-run

`--expenses` marks costs paid from the user's own pocket.

## 4. Warnings and errors

Workbench checks entries like the web form. A warning stops with its
message and code (e.g. `maybe-duplicate`, `take-a-break`, `you-are-late`,
`hours-for-invoicing-lower`). Show the message to the user and pass
`--ignore-warning <code>` only after they confirmed the entry, or when they
told you beforehand to accept that warning. Errors (e.g. hours of past
weeks, a project closed too long ago, a service which doesn't allow logging
anymore) can't be ignored: tell the user, don't work around them.

## 5. Corrections

    wb hours update <id> --hours 1.5 --description "..." --dry-run
    wb hours delete <id> --dry-run
    wb costs update <id> ... / wb costs delete <id>

The IDs are in `wb hours search` and `wb costs search`. Hours of past weeks
and invoiced entries can't be changed or deleted anymore (except for their
description); confirm deletions with the user first.

## 6. Moving entries to another service

Entries logged on the wrong service move with `--service`, also to a service
of another open project:

    wb hours update <id> --service <service_id> --dry-run
    wb costs update <id> --service <service_id>

Several entries of one project move to another service of the same project
at once (all or none):

    wb hours move --project <project_id> --entry <id> --entry <id> --service <service_id> --dry-run
    wb costs move --project <project_id> --entry <id> --service <service_id>

Invoiced entries keep their service, entries of closed projects stay where
they are; tell the user instead of logging them again. Show the entries and
the target service to the user and wait for their approval before moving.

## 7. Breaks

Breaks count for the working time, and `take-a-break` warns when a day
has too much work without them. If the user took a break that isn't
logged (e.g. a gap between timestamps), log it instead of ignoring the
warning:

    wb breaks create 12:00 12:45 Lunch --dry-run
    wb breaks create 15:00 15:10 --day 2026-11-26
    wb breaks update <id> --ends-at 13:00
    wb breaks delete <id>

`wb breaks` lists the user's breaks of this week. Only their own breaks
can be changed or deleted, and breaks have to be logged promptly.
