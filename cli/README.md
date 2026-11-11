# Workbench CLI

Commands follow the pattern `wb <noun> <verb>`, e.g. `wb projects search` or
`wb offers create`. `wb --help` and `wb <noun> --help` list them all. `search`
takes optional search terms and filters such as `--project`, `--customer` or
`--owned-by`; `show` takes an ID.

Searches show 100 results by default and tell you when there are more.
`--limit` (at most 10000) and `--offset` page through them, e.g.
`wb invoices search --open --limit 50 --offset 50`. With `--json` the results
are in `items` and `count` is the number of all matches. `--csv` writes one
row per result for spreadsheets, nested objects become columns like
`project.code`; reports write the rows of their main table. Combined with
`--limit`, e.g. all hours of last month:

    wb hours search --period last-month --limit 10000 --csv > hours.csv

Searches and reports of a period take `--period`: a year (`2026`), a month
(`2026-09`), a quarter (`2026-Q3`) or relative to today (`last-week`,
`this-month`, `next-quarter`, `last-year` etc.). `--since` and `--until`
override its start and end, or are used on their own. Cutoff dates are given
with `--date`.

The `wb` program talks to the Workbench JSON API. Install it with
[uv](https://docs.astral.sh/uv/):

    uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"

Upgrade it when `wb` tells you to, it prints the command. `--python` switches
to a newer Python when `wb` needs one, `uv tool upgrade` fails otherwise:

    uv tool upgrade --python 3.15 workbench-cli

Enable completing commands, options and installations with Tab in your shell:

    echo 'eval "$(wb completion bash)"' >> ~/.bashrc     # bash
    echo 'eval "$(wb completion zsh)"' >> ~/.zshrc       # zsh
    wb completion fish > ~/.config/fish/completions/wb.fish   # fish

Options which expect short names or teams (`--owned-by`, `--user`, `--team`
etc.) are completed too; the names are fetched once a day and cached in
`~/.cache/wb`.

Log in, which opens the browser to authorize `wb`. Choose the access
explicitly: `--read` only allows looking things up, `--write` also allows
changes like creating offers or closing deals. Read access is the safer choice
for tools and agents which only answer questions:

    wb login https://workbench.feinheit.ch --read
    wb login https://workbench.feinheit.ch --write

Check it with `wb me`. Access expires 30 days after its last use; `wb` then
opens the browser again by itself and asks for the same access. On computers without a
browser, create a token in Workbench ("API tokens" in the user menu, choose its
access there) and use `wb login URL --token`.

Logging in to another installation adds it and makes it the current one.
Switch between them with any unique part of their URL:

    wb auth list
    wb auth switch feinheit

The URLs and the tokens are stored in `~/.config/workbench.toml`. Switching
changes the installation for all terminals. To work with another
installation in one terminal only, set `WORKBENCH_URL` there to an
installation you're logged in to, or use `--installation` (`-i`, any unique
part of its URL) for a single command. Commands which don't use the current
installation say so on stderr:

    export WORKBENCH_URL=https://workbench.example.com
    wb -i example offers guidelines --set ~/notes/offer-guidelines.md

## What's on your plate

`wb me` shows who you are, your open projects, this week's planned work, and
the offers, invoices and deals which may need action (the latter depending on
your features).

## Users

`wb users search` finds users by name, short name or email address, e.g. for
the short names which filters like `--owned-by` expect. `--include-inactive`
also lists inactive users.

    wb users search
    wb users search hans --include-inactive

`wb teams search` lists teams with the short names of their members, e.g. for
the `--team` option of reports:

    wb teams search
    wb teams search design

## Creating projects

Find the customer and the contact, then create the project. Projects are
validated like in the web interface; where the web interface would show a
warning, the CLI fails and shows the warning's code. Ignore exactly the
warnings you checked with `--ignore-warning CODE` (may be repeated), a
different warning still fails:

    wb projects update 1234 --close --ignore-warning no-contact

    wb contacts search beispiel
    wb projects create --title "Online Marketing 2027" --contact 345 --dry-run
    wb projects create --title "Online Marketing 2027" --contact 345

Projects are changed field by field, closed and reopened the same way:

    wb projects update 1234 --title "Online Marketing 2028" --owned-by mk
    wb projects update 1234 --close --dry-run
    wb projects update 1234 --reopen

Closing a project discards its offers in preparation; if they have planned
work, decide with `--delete-planned-work` or `--keep-planned-work`.

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
  - type: Home
    email: hans.muster@example.org
phone_numbers:
  - type: Mobile
    phone_number: 079 123 45 67
postal_addresses:
  - street: Bahnhofstrasse
    house_number: "1"
    postal_code: "8001"
    city: Zürich
```

    wb people create person.yaml --dry-run
    wb people create person.yaml

People are searched like on the people list of the web interface, e.g. the
members of a group (also through their organization) or people without any
active group:

    wb people search --group "Newsletter"
    wb people search --without-groups --primary-contact mk
    wb people search --group "Newsletter" --missing-postal-address
    wb people search --projects-or-deals-since 2023-01-01 --csv

`wb people update` changes the names, the salutation, the notes, the primary
contact and the groups of a person or archives them, e.g. someone who left;
`wb organizations update` changes the name, the notes, the billing address and
the groups of an organization:

    wb people update 1234 --primary-contact mk --add-group "Newsletter"
    wb people update 1234 --salutation "Liebe Anna" --first-name-terms
    wb people update 1234 --archive
    wb organizations update 45 --name "Beispiel AG" --add-group "Agenturen"
    wb organizations create "Neu AG" --email info@example.com --dry-run

People whose primary contact left get new ones from their projects and deals
(the lead of the latest project or the owner of the latest deal, the person's
own before their organization's), or all of them go to one person:

    wb people reassign-suggestions --from ab --since 2023-01-01
    wb people reassign --from ab --suggested --since 2023-01-01 --dry-run
    wb people reassign --from ab --to cd
    wb people reassign --suggested --since 2023-01-01 --dry-run   # everyone who left

Cleaning up the address book (the workbench-address-book skill walks through
it): possible duplicates and generic addresses like info@ of several people,
which belong to the organization; organizations whose people have different
postal addresses, e.g. old ones, which are changed for several people at once:

    wb people duplicates
    wb people merge 345 --into 123 --dry-run
    wb organizations merge 67 --into 45 --dry-run
    wb people shared-emails
    wb organizations update 45 --email info@example.com
    wb people update 123 --remove-email info@example.com
    wb people shared-phones
    wb organizations update 45 --phone-number "+41 44 123 45 67"
    wb people update 123 --remove-phone "+41 44 123 45 67"
    wb people update 123 --organization 45 --ignore-warning organization-update
    wb people update 123 --remove-postal-address 678
    wb people update 123 --postal-address-type 679 Home
    wb people update 123 --email-type 680 Home --phone-type 681 Mobile
    wb organizations search --several-postal-addresses
    wb organizations show 45
    wb organizations change-address 45 --address 789 --street Neuweg --house-number 2
    wb people change-address 123 --address 679 --street Neuweg --house-number 2
    wb organizations search --without-active-people

Groups are listed, created and archived with `wb groups`:

    wb groups
    wb groups create "Newsletter 2027"
    wb groups update 56 --archive

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
    wb projects search --customer 345 --owned-by mk --include-closed
    wb projects show 1234

Print everything needed to write the offer: the project, its existing offers,
the service types with their hourly rates and the JSON schema of an offer.
Hand this to an LLM together with the specification of the offer:

    wb offers context 1234 > context.json

Your organization's own rules for offers (factors from past projects,
templates, a checklist) usually contain confidential figures, so they aren't
part of Workbench. Point wb to a file of your own, per installation, and the
`workbench-offer` skill follows it:

    wb offers guidelines --set ~/notes/offer-guidelines.md
    wb offers guidelines            # Prints the file, says which one on stderr
    wb offers guidelines --clear

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

`wb offers show` lists the IDs of the services and the totals:

    wb offers search --project 1234
    wb offers search relaunch --status offered
    wb offers show 5678
    wb offers pdf 5678 --signature-line -o ~/Downloads
    wb offers update 5678 --title "Relaunch 2027" --description - < text.txt
    wb offers update 5678 --discount 500 --dry-run

External references (URLs of issues or pull requests, for example) can be
changed for any offer, also when it has been accepted already. They replace
the existing ones; Workbench only stores them and doesn't talk to GitHub:

    wb offers update 5678 --external-reference https://github.com/org/repo/issues/12 --external-reference https://github.com/org/repo/pull/13
    wb offers search --external-reference https://github.com/org/repo/issues/12

Services are created, changed, moved, deleted and reordered one by one with
`wb services`, with the rules of the web interface: services of offers which
have been sent or accepted can't be changed anymore, only their external
reference can; services are only moved to offers in preparation or service
groups; services with logged hours or costs can't be deleted. `--dry-run`
validates without saving anything:

    wb services create --offer 5678 --title "Newsletter" --service-type "Programmierung & IT" --hours 12 --after 901 --dry-run
    wb services create --project 1234 service.yaml
    wb services update 902 --hours 20 --description "Incl. testing"
    wb services update 903 --clear-cost --optional
    wb services update 902 --external-reference https://github.com/org/repo/issues/12
    wb services update 902 --offer 5678
    wb services update 902 --clear-offer
    wb services update 902 --title "#12 Title of the issue"
    wb services delete 904
    wb services reorder 903 901 902

`reorder` takes all services of one offer, or all services without offer of a
project, in the new order.

Logged hours and costs are reassigned to another service of the project like
in the web interface; invoiced entries stay with their service unless they are
included:

    wb services reassign-logbook 902 --to 905 --dry-run
    wb services reassign-logbook 902 --to 905 --include-invoiced

Services are given with options or as YAML (or JSON) files like a service of
`wb offers create`; options override the file. `update` only changes the given
fields. Services with logged hours or costs can be changed but not deleted.

A new version of the whole offer replaces it, as long as no hours or costs
have been logged on its services:

    wb offers replace 5678 offer.yaml --dry-run
    wb offers replace 5678 offer.yaml

All commands which output data accept `--json`.

## GitHub milestones

Offers can be linked with GitHub milestones: the URLs of the milestones are
external references of the offer, one per repository. `wb milestones` uses the
GitHub CLI [`gh`](https://cli.github.com/) for GitHub, Workbench itself doesn't
talk to GitHub. Milestones without an offer, a new milestone for an offer,
linking an existing one, and a service group (without services yet) for a
milestone; the link to the offer is added to the milestone's description:

    wb milestones list acme/web acme/app --unlinked
    wb milestones create 5678 acme/web --title "Phase 2" --dry-run
    wb milestones link 5678 https://github.com/acme/web/milestone/3
    wb milestones offer 1234 https://github.com/acme/web/milestone/4

Every milestone should belong to one offer, `link` and `offer` refuse
milestones which are linked already unless you pass `--force`.

## Invoices

Search and show invoices, and save their PDF (under the invoice's file name
here, or `-o FILE_OR_DIRECTORY`):

    wb invoices search --open
    wb invoices search --overdue
    wb invoices search --project 1234 --since 2026-01-01
    wb invoices search hosting --customer 345
    wb invoices show 5678
    wb invoices pdf 5678

`wb invoices show` lists the services of the invoice with their offers
(fixed amount and down payment invoices have none).

The CLI only creates invoices in preparation, they are checked and sent in
the web interface:

    wb invoices create --offer 5678
    wb invoices create --project 1234 --type down-payment --subtotal 5000
    wb invoices create --project 1234 --subtotal 20000 --down-payment 5678
    wb invoices create --project 1234 --service 11 --service 12 --from-logbook
    wb invoices create --contact 345 --title Workshop --subtotal 1200

Overdue invoices to remind customers of, per customer and contact, like the
reminders in the web interface (without postponed reminders):

    wb invoices reminders
    wb invoices mark-reminded 5678 5679    # e.g. after sending a dunning letter
    wb invoices postpone-reminders 5678 2026-11-30
    wb invoices postpone-reminders 5678 2026-12-20 --confirm   # more than 30 days
    wb invoices postpone-reminders 5678 --clear

The planned invoicing (gross margin, without third party costs):

    wb projected-invoices search --project 1234
    wb projected-invoices search --since 2026-11-01 --until 2026-12-31

Recurring invoices, those which still renew by default (`--status closed` or
`all` for the others):

    wb recurring-invoices search hosting
    wb recurring-invoices search --customer 345 --status all

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

Change deals field by field, values by their type (`TYPE=` removes one), and
close them like in Workbench: accepting or declining a deal also accepts or
declines its related offers which haven't been accepted yet, unless you pick
them with `--offer` or pass `--keep-offers`:

    wb deals update 1234 --probability high --decision-expected-on 2026-12-15
    wb deals update 1234 --value Design=6000 --value Hosting= --dry-run
    wb deals close 1234 accepted --closing-type "Direct award"
    wb deals close 1234 declined --closing-type "Too expensive" --notice "Chose a cheaper agency" --keep-planned-work
    wb deals reopen 1234

Link offers to open deals and unlink them, by ID or code. Only offers which
are in preparation, service groups or offered can be linked; offers of other
customers' projects are a warning which has to be ignored explicitly (e.g.
when the deal is with an agency):

    wb deals offers add 1234 2026-0179-o02 2026-0179-o03 --dry-run
    wb deals offers add 1234 5678 --ignore-warning other-customer
    wb deals offers remove 1234 2026-0179-o02

Deals accepted and declined in a period (this week by default), and who
changed which deals:

    wb deals stats --period 2026-Q3
    wb deals stats --period 2026 --user mk
    wb deals history --since 2026-10-01

## Notes

Notes on deals, invoices, recurring invoices and projects, e.g. the results
of a project's debriefing. Search all of them or those of some objects:

    wb notes search budget
    wb notes search --deal 1234
    wb notes create --deal 1234 --title "Call" --description "Budget approved."
    wb notes create --project 4321 --title "Debriefing" --description - < debriefing.md

Like in Workbench, adding a note notifies the owner of the object.

## Services

Services with their hours and costs, and what has been logged on them so far.
Rates are shown with the offers (`wb offers show`) and the project statistics;
`--json` has the hourly rate too (with the controlling feature) and splits the
logged hours into invoiced and not invoiced ones.

    wb services search --project 1234
    wb services search --offer 5678
    wb services search hosting
    wb services search --external-reference https://github.com/org/repo/issues/12

## Logged hours and costs

Hours and costs are logged in Workbench, its forms warn about many mistakes.
Searching them works in the CLI:

    wb hours search --project 1234
    wb hours search --rendered-by mk --since 2026-10-01
    wb hours search --project 1234 --period last-month
    wb hours search wireframes --customer 345
    wb hours search --project 1234 --not-invoiced
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

Create absences like in Workbench, your own by default:

    wb absences create --starts-on 2026-12-21 --ends-on 2026-12-31 --days 5 \
        --reason vacation --description "Christmas holidays" --dry-run

## Reports

The reports require the same features as in the web interface, most of them
the controlling feature. Key figures:

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

Productivity of the last month by default, requires the productivity feature:

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

[`skills/`](skills/) contains [Claude Code](https://claude.com/claude-code)
skills for common Workbench tasks: offers, contacts, cleaning up the
address book, deals, planning, mailing lists and controlling summaries. See its README for what they do and how to install
them.

## Bug reports

When `wb` crashes or Workbench fails, `wb` writes a bug report with the
command, the versions and the traceback or the server's response to
`~/.cache/wb/` and tells you where it is. Send it to the people running
Workbench. Set `WB_DEBUG=1` to get the exception instead.
