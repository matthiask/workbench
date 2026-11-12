# Claude Code skills for Workbench

[Claude Code](https://claude.com/claude-code) skills which do common
Workbench tasks through the `wb` CLI. They prepare and propose, people
decide: the skills look for existing records before creating new ones,
validate every change with `--dry-run` and only write after the user
explicitly approves. They stick to what the user and the data say and ask
instead of guessing.

All of them need `wb`, logged in with `wb login URL --write` (`--read` is
enough for looking at things and for controlling summaries). If `wb` only
has read access, the skills ask the user to log in again instead of working
around it. Workbench checks the user's features like in the web interface.

Link them into your personal skills to use them in any directory (from the
repository root, again when skills are added):

    for skill in "$PWD"/cli/skills/workbench-*/; do ln -sfn "${skill%/}" ~/.claude/skills/; done

## workbench-address-book

Cleans up the address book: merges duplicate people and organizations
(`wb people duplicates`, `wb organizations duplicates`), reassigns the
people of users who left, moves generic email addresses like info@ from
people to their organization's
central or accounts payable address, changes outdated postal addresses of
an organization's people at once and archives organizations without active
people. It shows its findings in batches, proposes which duplicate to keep
and asks whenever it isn't obvious; merging and archiving only happen after
the user's approval.

## workbench-contact

Adds people and their organizations from unstructured data such as email
signatures, business cards, web pages or pasted addresses. It first searches
for the person, their email address and their organization, and then
creates the person with `wb people create`, linked to the existing
organization or with a new one. The API rejects duplicate names and email
addresses; the skill shows them and only creates a duplicate if the user
confirms that it's someone else.

For existing people it only adds new email addresses, phone numbers and
postal addresses (`wb people add-details`). It never changes or removes
existing details; other changes are made in Workbench. It doesn't guess
email addresses, phone numbers or genders.

## workbench-controlling

Writes controlling summaries, e.g. a monthly summary for the management or
the team, from the reports: key data, cash data, project budgets, projected
gross margin, third party costs, hours and deals. Requires the controlling
feature and only reads; reports the user can't access are left out. It
knows the pitfalls of the figures, e.g. that gross margin is not profit and
must never be subtracted from revenue, and leads with what needs attention.
It reads the notes of overdue invoices for payment promises and disputes.

Payment reminders to customers are only sent on explicit request, after
showing the recipient and the invoices; that requires the bookkeeping
feature.

## workbench-deals

Keeps the sales pipeline up to date. Requires the deals feature. It lists
the open deals with their notes, points out stale ones (decisions expected in
the past, missing dates or values, no notes for a long time) and asks the
user what they know. It then updates probabilities, decision dates and
values, adds notes (which notify the deal's owner) and closes deals as won
or lost, which also accepts or declines their offers like in Workbench. It
links offers to open deals and unlinks them.

It changes only what the user told it, and never closes, declines or reopens
deals on its own or invents values, probabilities, dates or reasons.

## workbench-mailing-list

Maintains a group of people for a mailing, e.g. Christmas cards, gifts or
invitations. Workbench is the source of truth and the list for the mailing is
an export of the group. It looks at the members (archived people usually
left, so it proposes others from the same organization), finds who is
missing (contacts of recent projects and deals, people in no group yet) and
presents the candidates by their primary contact, so that everyone decides
about the people they know. It can import an old spreadsheet once.

It only adds what's missing: people to the group, postal addresses to people
without one, primary contacts where the current one isn't active anymore. It
shows differences instead of overwriting them and never archives people or
groups without being told to.

## workbench-offer

Turns a specification, a briefing or an email into an offer for a project,
or revises an offer which is still in preparation. It finds the project (or
creates it after asking), reads the context of the project — service types
with their hourly rates, the existing offers whose wording and structure it
reuses, a flat rate, the notes of the project and its deals — and drafts the
offer as YAML. It follows your private offer guidelines if you configured a
file with `wb offers guidelines --set PATH` (see the CLI README). It shows
the draft as a table with its assumptions and open questions, and creates it
with `wb offers create`. Afterwards it suggests linking the offer to the
customer's open deal, after asking which one. Revisions change single
services with `wb services create/update/delete/reorder` and headings with
`wb offers headings create/update/delete`.

Offers created this way are always in preparation: people check and send
them in Workbench, the skill never sends anything to customers and doesn't
invent rates or discounts.

## workbench-planning

Plans projects: milestones and planned work per person and week, from the
offers' services, a timeline and the capacity of the people. It reads the
planning context (offers, people with their planning hours, absences,
existing planning) and the project's notes, checks the free capacity of
teams and people, and imports the plan with `wb planning import`. Single
planned work can be changed too, e.g. made definitive once a deal is won,
moved or removed. It also answers who has time when, which only needs read
access. It offers to record why work was rescheduled or added as a note on
the project.

New work is provisional unless the user says otherwise. The import doesn't
check capacity; the skill does that itself. The import context is
deliberately free of personal data: people are identified by their short
name and absences have no reason.
