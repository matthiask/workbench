---
name: workbench-deals
description: Keep the Workbench sales pipeline up to date with the `wb` CLI. Use when the user wants to review, update, clean up, close, win or lose deals, update probabilities or expected decision dates, link offers to deals, find accepted offers or maintenance counted twice next to their deal, link projects to deals, create deals for accepted or offered offers and maintenance without deal (so that their values count by value type and the funnel shows them), or asks about the state of the pipeline or of a deal in Workbench.
---

# Keeping the Workbench sales pipeline up to date

The `wb` CLI talks to Workbench (see `wb --help`); deals require the deals
feature. If `wb` isn't installed or configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`. Only looking at deals works with `--read` too; if
`wb` answers that the token only allows reading, ask the user to log in with
`--write` instead of working around it.

## 1. Look at the pipeline

    wb deals search                          # Open deals, earliest decision first
    wb deals search --owned-by <short name>
    wb deals search --period this-month      # Decision expected (or closed) this month
    wb deals show <deal_id>
    wb notes search --deal <deal_id>         # What happened so far

Point out what looks stale:

- Open deals whose expected decision is in the past.
- High probability deals without an expected decision date.
- Deals without notes for a long time, deals whose values are missing.

Summarize per owner and ask the user what they know about each deal. Don't
guess outcomes, probabilities or dates; the user or the deal's owner knows.

## 2. Update deals

Change only what the user told you, one command per deal, first with
`--dry-run`:

    wb deals update <deal_id> --probability high --decision-expected-on 2026-12-15 --dry-run
    wb deals update <deal_id> --value Design=6000 --value Hosting= --dry-run

- `--value TYPE=AMOUNT` sets the value of a value type, `TYPE=` removes it.
  `wb deals value-types` lists the value types, `wb deals attributes` the
  attribute groups and attributes `--attribute GROUP=ATTRIBUTE` takes.
- High probability requires an expected decision date.
- Contributions say who won the deal: the accepted deals report (`wb deals
  stats`) splits a deal's value between its contributors by weight (100 main
  driving force, 50 contributing force). `wb deals show` lists them;
  `--contribution ab=100 --contribution cd=50` sets them, `cd=0` removes
  one. The owner always contributes; a new owner (`--owned-by`) takes over
  the old owner's contribution unless you change either of them in the same
  command. Ask the user who contributed when a deal is won or changes hands.
- Add what you learned as a note so others see it:
  `wb notes create --deal <deal_id> --title "<title>" --description "<text>"`.
  The deal's owner is notified by email, mention that to the user.

## 3. Link offers

Closing a deal accepts or declines its related offers, so link the offers
which belong to an open deal, e.g. after creating them with `wb offers
create`. Offers are given by ID or code (`wb deals show` prints codes):

    wb offers search --customer <organization_id>   # Newest first
    wb deals offers add <deal_id> <offer> ... --dry-run
    wb deals offers remove <deal_id> <offer> ... --dry-run

- Open deals take offers in preparation, service groups and offered offers;
  accepted deals take all offers which haven't been declined, e.g. the
  detailed offer of the contract the deal sums up (nothing changes, the
  offer keeps its status, see below). Only
  open deals can be unlinked from. Linking an offer twice or removing one
  which isn't linked is an error.
- Offers of another customer's projects (agencies and their clients,
  departments of the same city) are rejected; add `--ignore-warning
  other-customer` only after the user confirmed the link.
- Ask the user which deal an offer belongs to when the customer has several
  open deals.

### Accepted offers without deal

The accepted deals report (`wb deals stats`) counts accepted offers without
deal on their own, since deals come first and offers later in the funnel.
An accepted offer which belongs to an accepted deal but isn't linked to it is
counted twice. Look for them in reviews, e.g. for the last quarter (the
period of offers filters the offer date, so look further back and compare
their `closed_on`):

    wb offers search --status accepted --without-deal --since 2026-04-01 --json
    wb deals search --status accepted --period last-quarter --json

Compare by customer (the offer's project's customer), closing date, title
and amount: offers count `total_excl_tax`, deals their `value`. Several
offers of a project closed on the same day often add up to one deal.

- A deal whose linked offers (`wb offers show` has their totals) already
  reach its value is full: further offers of the project are follow-up
  orders and count on their own.
- A deal with a gap takes the offers which fill it; when several fit, take
  the oldest ones.
- A deal which already has offers of its own isn't a duplicate of an offer
  for different work, even if the amounts match.
- Campaigns and mandates are often sold months before their offers are
  accepted (e.g. a campaign for next year): also compare deals without
  offers from up to a year earlier, by title.
- When unsure, link: an offer linked to a smaller deal only counts the
  deal, which underestimates, and that's preferred over counting twice.

Present the likely pairs to the user, the clear ones (same customer, amounts
within a few percent, closed within days) first, and link each pair only
after the user confirmed it:

    wb deals offers add <deal_id> <offer> ... --dry-run

Never link on your own: an offer for the same customer may well be a
follow-up order which is won business of its own.

### Maintenance without deal

The report also counts what was invoiced on maintenance projects without
accepted offer and without deal, credited to the project owner. Catch-all
deals summing up such work for the statistics aren't needed anymore; don't
create new ones. A deal which sells maintenance or a mandate without offer
links its project instead, so that its invoices aren't counted a second
time; this also works for accepted deals and changes nothing else:

    wb deals projects add <deal_id> <project> ... --dry-run
    wb deals projects remove <deal_id> <project> ... --dry-run

To find maintenance which a deal already covers, compare the projects of
`wb deals stats --period <period> --json` (`maintenance_without_deal`) with
the accepted deals of the same customers which have no offers and no
projects (`wb deals show`), e.g. a maintenance contract deal next to a
maintenance project with about the same yearly amount. Suggest the links,
link only after the user confirmed each one. Deals which only existed for
the statistics are the user's call: ask before declining or deleting
them.

## 4. Deals for everything that's going on

The accepted deals report counts offers and maintenance without deal, but
only in their sum: they have no value type, so the targets per value type
(e.g. programming) don't see them. The funnel only sees open deals. When the
user wants the pipeline to show all the work, sold or about to be, create
the missing deals from what Workbench already knows. Each deal is linked to
what it's made from, so nothing is counted twice.

### Values by value type

Deal values are gross margin: an offer's services without their third party
costs, after the discount (spread over the services in proportion). Split
them by value type using the services' `service_type` (`wb offers show
<offer> --json`), or their `effort_type` when the rate deviates from the
service type's and `service_type` is empty. Propose a mapping from service types to `wb deals
value-types` once, e.g. programming services to programming and project
management to the value type of the work it manages, let the user correct
it, then use it for the whole session. Consulting, concepts and project
management usually follow the project: web consulting when it includes
programming, communication consulting otherwise. Flat rate services and
services without effort type are assigned by their titles (a "Paketpreis
Website" is programming and web consulting, half each unless the hours say
otherwise). Services which fit no value type are the user's
call; never drop them silently.

### Attributes and contributions

Required attributes (`wb deals attributes`) come from the customer's earlier
deals (`wb deals search --customer <id> --status accepted`, same industry;
the source of follow-up orders is usually existing customers). Ask when the
customer has no earlier deals. The offer's or project's owner owns the deal;
ask who takes over for owners who left, and who else contributed only when
the user wants to.

### Accepted offers without deal

    wb offers search --status accepted --without-deal --period <period> --json

First check each offer against the accepted deals as in section 3, from
the period's start on without an end (`--since` only: mandates close at the
start of their period, e.g. on 2027-01-01, and may already have their deal),
and against the open ones: an offer
which belongs to an existing deal gets linked, not a new deal. For the rest,
one deal per offer (or per project, for offers of a project accepted the
same day):

    wb deals create --title "<offer title>" --customer <id> --owned-by <owner> \
      --probability high --decision-expected-on <closed_on> \
      --value "<type>=<amount>" ... --attribute "<group>=<attribute>" ... \
      --description "Created from offer <code>" --dry-run
    wb deals close <deal_id> accepted --closing-type "<type>" --closed-on <offer closed_on> --keep-offers --dry-run
    wb deals offers add <deal_id> <offer> --dry-run

Accepted deals take accepted offers, so close the deal before linking.
The closing date is about when the work can start: usually the offer's
closing date, but mandates and maintenance for a period (a year, a quarter,
"… 2027") are closed on the start of that period, even when the offer was
accepted earlier, and open ones expect the decision then. Follow-up orders are mostly direct requests without competition;
ask when unsure.

### Maintenance without deal

    wb deals stats --period <period> --json     # maintenance_without_deal
    wb projected-invoices search --period <period> --json

The stats find what was invoiced; the planned invoicing also finds what's
expected. Before creating a deal, also search the deals by title (`wb deals
search "Wartung 2026" --status accepted`): earlier deals for the same
maintenance may be filed under a slightly different customer or link other
projects of it. Its projects which are maintenance (`wb projects show <id>
--json`: `type`) and have no accepted or offered offer (`offers`) nor a
deal (`deals`, linked directly or through an offer) are candidates too,
before anything is invoiced. Planned invoicing is
gross margin already, like deal values.

Most maintenance projects are yearly mandates ("… 2027") and get one deal
for what they're expected to bring in that year. A linked project's
invoices count with the deal only, **in all periods**: for the rare project
running for several years, linking it also removes its earlier invoices
from the report. Point those out and leave them alone unless the user
decides otherwise.

The value is the project's planned invoicing for the period (`wb
projected-invoices search --project <id> --period <period>`), which is
already a conservative estimate; without any, what was invoiced in the
previous period, rounded down. Don't correct
it upwards later unless the difference is large. Split it by value type
by who did the work: the hours logged on the projects (`wb hours search
--project <id>`) by the `value_type` of each person's specialist field
(`wb users --json`, `--include-inactive` for people who left); hours of
people without one (e.g. interns) are left out of the split. Maintenance deals are
closed on the start of their period (`--closed-on 2026-01-01` for 2026), not
on the first invoice; mandates sold before the period starts are open deals
with high probability and the period's start as decision date, accepted
when the period starts, with that date. Group them by customer and period
(one deal "<customer> – Wartung & Support 2026" linking all its maintenance
projects of the year) and leave customers with only a few thousand francs a
year as maintenance without deal.

Recurring invoices are mostly third party costs passed on (hosting,
licenses) and have little gross margin: ignore them unless their margin is
significant, then treat them like maintenance.

### Offered offers without deal

    wb offers search --status offered --without-deal --json

Offers sent long ago whose validity has expired belong to their owners for
declining, not into the funnel: list them separately. Several offers of a
project sent together (areas, quarters of a mandate) make one deal. Compare the
others with all deals of the customer by title and amount, the open ones and
the accepted ones of the last year, deals without offers included: the
owner may have created the deal before the offer. An open or accepted deal takes
the offer (an accepted one keeps the offer's status: the deal sums up the
contract, the offer details it). Only the rest get new
open deals with the offer linked, so the funnel sees them: probability and
decision date from the user, or normal and the offer's `valid_until` as a
proposal. Closing the deal later accepts or declines the offer; an offer
accepted on its own leaves its deal open, so look for open deals whose
offers are all settled and close them like the offers.

### Present before creating

List the proposed deals in a table (customer, title, owner, values per value
type, attributes, closing date, what gets linked) and create them only
after the user approved the list, one `--dry-run` per command first. Deals
created this way are visible to everyone like any other deal, and count in
the outreach report of their contributors; mention that.

## 5. Close deals

Closing works like in Workbench: accepting or declining a deal also accepts
or declines its related offers which haven't been accepted yet.

    wb deals close <deal_id> accepted --closing-type "<award of contract>" --dry-run
    wb deals close <deal_id> declined --closing-type "<reason>" --notice "<why>" --dry-run
    wb deals reopen <deal_id>

- `wb deals closing-types` lists the closing types; ask the user which one
  applies, especially the reason for losing.
- `--offer <offer_id>` (repeatable) picks the offers to accept or decline,
  `--keep-offers` leaves them alone. Show the user which offers would change.
- Declining offers with planned work needs `--delete-planned-work` or
  `--keep-planned-work`; ask the user.

## Rules

- Deleting deals (`wb deals delete <deal> --dry-run`) is only for duplicates
  and mistakes, and only after the user confirmed each one: deals which were
  lost are declined, so that the reports keep them.

- Run every change with `--dry-run` first, show the user what changes and
  only run it without `--dry-run` after their explicit approval.
- Never close, decline or reopen deals on your own, and never invent values,
  probabilities, dates or reasons. Values derived from offers, invoices and
  the planned invoicing (section 4) are proposals the user approves.
- `wb deals stats --period last-month` and `wb deals history --period
  this-week` show what was won, lost and changed, e.g. for a weekly review.
