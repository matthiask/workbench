# Workbench CLI

Commands follow the pattern `wb <noun> <verb>`, e.g. `wb projects search` or
`wb offers create`. `wb --help` and `wb <noun> --help` list them all. `search`
takes optional search terms and filters such as `--project`, `--customer` or
`--owned-by`; `show` takes an ID.

Searches show 100 results by default and tell you when there are more.
`--limit` (at most 10000) and `--offset` page through them, e.g.
`wb invoices search --open --limit 50 --offset 50`. With `--json` the results
are in `items` and `count` is the number of all matches.

Searches and reports of a period take `--period`: a year (`2026`), a month
(`2026-09`), a quarter (`2026-Q3`) or relative to today (`last-week`,
`this-month`, `next-quarter`, `last-year` etc.). `--since` and `--until`
override its start and end, or are used on their own. Cutoff dates are given
with `--date`.

The `wb` program talks to the Workbench JSON API. Install it with
[uv](https://docs.astral.sh/uv/):

    uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"

Upgrade it when `wb` tells you to:

    uv tool upgrade workbench-cli

Enable completing commands, options and installations with Tab in your shell:

    echo 'eval "$(wb completion bash)"' >> ~/.bashrc     # bash
    echo 'eval "$(wb completion zsh)"' >> ~/.zshrc       # zsh
    wb completion fish > ~/.config/fish/completions/wb.fish   # fish

Log in, which opens the browser to authorize `wb`:

    wb login https://workbench.feinheit.ch

Check it with `wb me`. Access expires after 30 days; `wb` then opens the
browser again by itself. On computers without a browser, create a token in
Workbench ("API tokens" in the user menu) and use `wb login URL --token`.

Logging in to another installation adds it and makes it the current one.
Switch between them with any unique part of their URL:

    wb auth list
    wb auth switch feinheit

The URLs and the tokens are stored in `~/.config/workbench.toml`. The
`WORKBENCH_URL` and `WORKBENCH_TOKEN` environment variables take precedence;
`WORKBENCH_URL` alone uses another installation you're logged in to for a
single command. `wb` doesn't log in again by itself when `WORKBENCH_TOKEN` is
used.

## What's on your plate

`wb me` shows who you are, your open projects, this week's planned work, and
the offers, invoices and deals which may need action (the latter depending on
your features).

## Users

`wb users search` finds users by name, short name or email address, e.g. for
the short names which filters like `--owned-by` expect. `--all` includes
inactive users.

    wb users search
    wb users search hans --all

## Creating projects

Find the customer and the contact, then create the project. Projects are
validated like in the web interface; where the web interface would show a
warning, the CLI fails and you have to use the web interface.

    wb contacts search beispiel
    wb projects create --title "Online Marketing 2027" --contact 345 --dry-run
    wb projects create --title "Online Marketing 2027" --contact 345

`wb organizations show 123` and `wb people show 345` show the details of the
search results, e.g. the people of an organization or the email addresses of a
person.

People are created from YAML (or JSON) files, e.g. written by an LLM from an
email signature (`wb people context` prints the schema). Pass `organization`
with the ID of an existing organization or `new_organization` with a name to
create one:

```yaml
given_name: Hans
family_name: Muster
address: Herr
salutation: Lieber Hans
new_organization: Beispiel AG
email_addresses:
  - email: hans@example.com
  - type: private
    email: hans.muster@example.org
phone_numbers:
  - type: mobile
    phone_number: 079 123 45 67
postal_addresses:
  - street: Bahnhofstrasse
    house_number: "1"
    postal_code: "8001"
    city: Zürich
```

    wb people create person.yaml --dry-run
    wb people create person.yaml

People and organizations whose names exist already are rejected unless you
pass `--allow-duplicates`; email addresses which are in use are always
rejected.

Add email addresses, phone numbers and postal addresses to existing people
with a file of the same structure; existing details are never changed or
removed:

    wb people add-details 345 details.yaml --dry-run

The customer is the contact's organization unless you pass `--customer`.
`--type` is `order` (default), `maintenance` or `internal`, `--owned-by` takes a
short name and defaults to you.

## Creating offers

Find the project:

    wb projects search relaunch
    wb projects search --customer 345 --owned-by mk --all
    wb projects show 1234

Print everything needed to write the offer: the project, its existing offers,
the service types with their hourly rates and the JSON schema of an offer.
Hand this to an LLM together with the specification of the offer:

    wb offers context 1234 > context.json

Offers are written in YAML (or JSON):

```yaml
title: Relaunch
description: |
  Concept, design and implementation of the new website.
services:
  - title: Concept
    service_type: Konzept    # Fills in the effort type and the hourly rate
    hours: 16
  - title: Design
    effort_type: Design      # Free effort type and rate
    hourly_rate: 185
    hours: 40
  - title: Hosting 2027
    cost: 1200
    third_party_costs: 1200
  - title: Newsletter integration
    service_type: Programmierung & IT
    hours: 12
    is_optional: true
```

Validate it and look at the totals, then create the offer. Offers are always
created in preparation; review and send them in Workbench.

    wb offers create 1234 offer.yaml --dry-run
    wb offers create 1234 offer.yaml

Offers in preparation can be changed service by service. `wb offers show`
lists the IDs of the services; every change shows the offer with its new
totals, `--dry-run` without saving anything:

    wb offers search --project 1234
    wb offers search relaunch --status offered
    wb offers show 5678
    wb offers update 5678 --title "Relaunch 2027" --description - < text.txt
    wb offers services add 5678 --title "Newsletter" --service-type "Programmierung & IT" --hours 12 --after 901 --dry-run
    wb offers services add 5678 service.yaml
    wb offers services update 5678 902 --hours 20 --description "Incl. testing"
    wb offers services update 5678 903 --clear-cost --optional
    wb offers services delete 5678 904
    wb offers services reorder 5678 903 901 902

Services are given with options or as YAML (or JSON) files like a service of
`wb offers create`; options override the file. `update` only changes the given
fields. Services with logged hours or costs can be changed but not deleted.

A new version of the whole offer replaces it, as long as no hours or costs
have been logged on its services:

    wb offers replace 5678 offer.yaml --dry-run
    wb offers replace 5678 offer.yaml

All commands which output data accept `--json`.

## Invoices

Invoices are read-only in the CLI:

    wb invoices search --open
    wb invoices search --overdue
    wb invoices search --project 1234 --since 2026-01-01
    wb invoices search hosting --customer 345
    wb invoices show 5678

Overdue invoices to remind customers of, per customer and contact, like the
reminders in the web interface (without postponed reminders):

    wb invoices reminders

The planned invoicing (gross margin, without third party costs):

    wb projected-invoices search --project 1234
    wb projected-invoices search --since 2026-11-01 --until 2026-12-31

## Deals

Deals require the deals feature:

    wb deals search                     # Open deals
    wb deals search --status accepted relaunch
    wb deals show 1234

Create deals like projects; you are their main driving force. Values are given
by value type and attributes by their group, unknown ones are rejected with a
list of the choices:

    wb deals create --title "Relaunch" --contact 345 --probability normal \
        --value Design=5000 --attribute Source=Referral --dry-run

Deals accepted and declined in a period (this week by default), and who
changed which deals:

    wb deals stats --period 2026-Q3
    wb deals stats --period 2026 --user mk
    wb deals history --since 2026-10-01

## Notes

Notes on deals, invoices and recurring invoices. Search all of them or those
of some objects:

    wb notes search budget
    wb notes search --deal 1234
    wb notes create --deal 1234 --title "Call" --description "Budget approved."

Like in Workbench, adding a note notifies the owner of the deal or invoice.

## Services

Services with their hours and costs, and what has been logged on them so far.
Rates are shown with the offers (`wb offers show`) and the project statistics.

    wb services search --project 1234
    wb services search --offer 5678
    wb services search hosting

## Logged hours and costs

Hours and costs are logged in Workbench, its forms warn about many mistakes.
Searching them works in the CLI:

    wb hours search --project 1234
    wb hours search --rendered-by mk --since 2026-10-01
    wb hours search --project 1234 --period last-month
    wb hours search wireframes --customer 345
    wb costs search --project 1234
    wb costs search --expenses --rendered-by mk

## Timestamps

`wb timestamps start` and `wb timestamps stop` replace the `tst` command of
workbench-tst. Both take an optional time (`13:30`) or minutes relative to now
(`-5`, `+15`) followed by notes:

    wb timestamps start
    wb timestamps stop -5 Wireframes review
    wb timestamps list
    wb timestamps list --day 2026-10-29

Stopping a task shows how long it took. `wb timestamps list` shows the day's
slices, the hours logged this week and since when the current task has been
running; the unlogged slices link to the form for logging their hours in
Workbench. `wb timestamps undo` deletes today's latest timestamp,
`wb timestamps delete T3` any other one by the code from the list (or by its
ID, add `--day` for codes of other days). The following timestamps are
renumbered, so the new list is shown afterwards. If you miss `tst`, add
`alias tst="wb timestamps"` to your shell's configuration.

## Absences

Current and upcoming absences of everyone, or of a period:

    wb absences search
    wb absences search --user mk --reason vacation --since 2026-01-01

## Reports

The reports require the same features as in the web interface, most of them
the controlling feature. Key figures as JSON:

    wb reports key-data
    wb reports key-data --month 2026-09
    wb reports cash-data --date 2026-09-30

Controlling, as tables or with `--json`:

    wb reports budget --owned-by mk
    wb reports budget --filter old-projects
    wb reports projected-gross-margin
    wb reports third-party-costs
    wb reports open-items --date 2026-09-30

Hours of a period, this week by default. `--user` (repeatable) and `--team`
filter the users:

    wb reports hours-per-customer --period 2026-Q3
    wb reports hours-per-customer --period last-month
    wb reports hours-per-type --period 2026-09 --team Design
    wb reports green-hours --since 2026-09-01 --until 2026-09-15
    wb reports planning-vs-logbook --user mk
    wb reports logging --period 2026-09

Annual working time per month, or per week until the current one. Your own
by default, someone else's by short name, or of all active users with the
controlling feature:

    wb reports working-time
    wb reports working-time --weekly
    wb reports working-time --year 2025 --user mk
    wb reports working-time --all

Gross margin per user and project of the last month by default, requires the
productivity feature:

    wb reports squeeze --period 2026-Q3

## Planning

Like offers: Fetch the context (offers, people, absences, existing milestones
and planned work, and the JSON schema of the import), let an LLM write the
plan, validate it and import it:

    wb planning context 1234 > context.json
    wb planning import 1234 plan.yaml --dry-run
    wb planning import 1234 plan.yaml

Importing only adds milestones and planned work, it never changes or removes
existing entries.

Export the planning of a project or a campaign, or of users or a team (the
next twelve weeks by default) with their
capacity per week. `--csv` writes one row per planned work and week, for
spreadsheets:

    wb planning export --project 1234
    wb planning export --campaign 56 --csv > campaign.csv
    wb planning export --team Design --period 2026-Q4
    wb planning export --user mk --since 2026-11-02 --until 2026-11-29

## Project statistics

Hours (offered, logged, planned), amounts (sold, invoiced, logged work which
hasn't been invoiced yet), gross margins, services, logged and planned hours
per person and invoices of projects. People are identified by their short
name.

    wb projects stats 1234 5678
    wb projects stats --open --closed-since 2026-01-01
    wb projects stats --open --json > stats.json
    wb projects stats --closed-since 2026-01-01 --csv > hours.csv

`--csv` writes one row per project, service and person with the logged hours.

## Claude Code skills

`skills/workbench-offer/` contains a [Claude Code](https://claude.com/claude-code)
skill which turns a specification into an offer using `wb`: it finds the
project, fetches the context, drafts the offer, reviews it with you, validates
it with `--dry-run` and only creates it after your approval.
`skills/workbench-contact/` adds people from email signatures, business cards
and the like, after looking for existing records. Link all of them into your
personal skills to use them in any directory (run it again when skills are
added):

    for skill in "$PWD"/cli/skills/*/; do ln -sfn "${skill%/}" ~/.claude/skills/; done

## Bug reports

When `wb` crashes or Workbench fails, `wb` writes a bug report with the
command, the versions and the traceback or the server's response to
`~/.cache/wb/` and tells you where it is. Send it to the people running
Workbench. Set `WB_DEBUG=1` to get the exception instead.
