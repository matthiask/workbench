---
name: workbench-offer
description: Turn a specification, briefing or email into a Workbench offer using the `wb` CLI. Use when the user wants to write, draft, estimate or create an offer (Offerte) for a Workbench project, or to revise an offer which is still in preparation.
---

# Creating Workbench offers from a specification

The `wb` CLI talks to Workbench (see `wb --help`). Offers created through it are
always **in preparation**. People review, adjust and send them in Workbench, so
the CLI never sends anything to a customer.

If `wb` isn't installed or configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`, which authorizes `wb` in the browser. Writing
needs `--write`; if `wb` answers that the token only allows reading, ask the
user to log in with `--write` instead of working around it.

## 1. Find the project

The offer belongs to an existing project. Ask for the project if it isn't
obvious, then search for it:

    wb projects search <terms>
    wb projects show <project_id>

If several projects match, ask which one. Don't guess.

If the project doesn't exist yet, find the customer and the contact and create
the project, after confirming title, customer and contact with the user:

    wb contacts search <terms>
    wb projects create --title "<title>" --contact <person_id> --dry-run
    wb projects create --title "<title>" --contact <person_id>

The customer is the contact's organization; pass `--customer` only for
people without one.

If Workbench rejects the project with a message which isn't about a specific
field, it's a warning of the web interface: ask the user to create the project
there instead.

## 2. Get the context

    wb offers context <project_id> > <scratchpad>/context.json

Read it before drafting anything:

- `service_types`: the usual effort types with their hourly rates.
- `offers`: the project's existing offers. Reuse their wording, structure,
  effort types and level of detail; they show how this customer gets offers.
- `project.flat_rate`: if set, every service uses this rate no matter what.
- `import_schema`: the exact JSON schema of an offer.

Read the notes of the project and of the customer's deals, they contain what
was discussed and agreed, e.g. in sales calls:

    wb notes search --project <project_id>
    wb deals search --customer <organization_id>
    wb notes search --deal <deal_id>

Then load the private offer guidelines, if the user has any:

    wb offers guidelines

They contain the organization's own rules for estimating and challenging
offers, e.g. factors from past projects, the share of project management,
templates and a checklist. Always tell the user in one line what happened,
so a wrong configuration doesn't go unnoticed:

- Loaded: name the file and the installation (`wb` prints both), e.g.
  "Using the offer guidelines from <file> for <installation>." Follow them:
  they take precedence over the general guidelines below. They are
  confidential, so never copy their figures, project names or customers into
  the offer, its descriptions or anything else leaving the conversation.
- None configured: say so for the installation and continue with the
  general guidelines below. Don't ask the user to configure any.
- Configured but missing (`does not exist`): tell the user and ask whether
  to continue without them.
- If `wb` says it uses another installation than the current one, mention
  that too.

## 3. Draft the offer

Write the offer as YAML to the scratchpad, e.g. `<scratchpad>/offer.yaml`:

```yaml
title: Relaunch
description: |
  Short summary of what the offer covers.
services:
  - title: Concept
    description: |
      What exactly is included.
    service_type: Konzept       # Fills in effort type and hourly rate
    hours: 16
  - title: Hosting 2027
    cost: 1200                  # Fixed amount instead of or on top of hours
    third_party_costs: 1200     # Part of the cost which is paid to third parties
  - title: Newsletter integration
    service_type: Programmierung & IT
    hours: 12
    is_optional: true           # Offered, but not part of the total
headings:                       # Optional, structure only (no amounts)
  - title: Operation
    description: From the launch on.
    before: 1                   # Index of the service it comes before
```

Guidelines:

- Write in the language of the specification and the existing offers (usually
  German). Titles are specific ("Konzept Navigation", not "Arbeit").
- Prefer `service_type` for hours. Service types are only suggestions:
  `effort_type` overrides the label, `hourly_rate` the rate. Only set
  `hourly_rate` when the specification or the user asks for a specific rate,
  never invent discounts.
- If the existing offers use rates which differ from the service types (e.g.
  a reduced rate for a nonprofit), ask the user which rates to use instead of
  silently picking either.
- One service per deliverable or phase, with a description saying what is and
  isn't included. Put assumptions and exclusions into the descriptions.
- Propose headings when the offer is longer or has a structure of its own,
  e.g. phases, areas or deliverables with several services each (as a rule
  of thumb from about eight services, or when the specification or the
  existing offers are structured like that). A short offer with a few
  services doesn't need any. Headings group the services which follow them
  and have no amounts and no subtotals.
- Estimate hours realistically, rather a bit high than too low. With
  guidelines, apply their factors and shares and say which ones you applied. Things the
  specification mentions as "maybe", "nice to have" or "later" become optional
  services.
- Licenses, hosting, stock images etc. are `cost`, with `third_party_costs`
  for what's passed on from third parties.
- Leave out `postal_address`; Workbench uses the project's contact.

## 4. Review with the user

Show the draft as a table (service, effort type, hours, rate, amount, optional)
with the headings as rows between the services and the totals, and list your
assumptions and open questions. If you added headings, say so, so that the
user can drop them or ask for a different structure. With
guidelines, go through their checklist and report what it flags. Then validate it
on the server, which also computes the totals:

    wb offers create <project_id> <scratchpad>/offer.yaml --dry-run

Fix any errors (they name the field, e.g. `services.2.hours`) and iterate
with the user until they're happy.

## 5. Create the offer

Only after the user explicitly approves:

    wb offers create <project_id> <scratchpad>/offer.yaml

Report the offer code and its URL. Remind the user that the offer is in
preparation and still has to be checked and sent in Workbench.

Then suggest linking the offer to the deal it belongs to, so that closing the
deal accepts or declines it. Look for the open deals of the project's
customer (`wb deals search --customer <organization_id>`, step 2 may already
have found them) and ask the user which one it is, even if there is only one;
never pick a deal on your own. If there is none, mention that and leave it.
After the user confirmed the deal:

    wb deals offers add <deal_id> <offer_code> --dry-run
    wb deals offers add <deal_id> <offer_code>

Only open deals accept offers. An offer of another customer's project (e.g.
the deal is with an agency, the project with its client) is rejected; only
add `--ignore-warning other-customer` if the user confirms the link is right.

## Revising an offer

Offers in preparation are changed service by service with `wb services`.
Look at the current offer first; its table shows the IDs of the services:

    wb offers show <offer_id>

Change only what was asked, one command per change, each one first with
`--dry-run`:

    wb offers update <offer_id> --title "<title>" --description - < <scratchpad>/text.txt
    wb services create --offer <offer_id> --title "<title>" --service-type "<type>" --hours 12 --after <service_id> --dry-run
    wb services create --offer <offer_id> <scratchpad>/service.yaml --dry-run
    wb services update <service_id> --hours 20 --dry-run
    wb services update <service_id> <scratchpad>/service.yaml --dry-run
    wb services delete <service_id> --dry-run
    wb services reorder <service_id> <service_id> ... --dry-run

- `update` only sends the given fields, everything else stays as it is.
  `--clear-hours` and `--clear-cost` remove values, `--optional` and
  `--no-optional` switch whether a service counts towards the total.
- A service file contains a single service like in step 3 (`title`,
  `description`, `service_type`, `hours`, `cost`, ...); options override it.
  Use files for longer descriptions.
- Show the user the change (the dry run prints the service; `wb offers
  show` shows the totals afterwards) and run the command without `--dry-run`
  only after their explicit approval.
- `reorder` needs the IDs of all services of the offer; headings stay in
  their place.
- Services with logged hours or costs can be changed but not deleted.
- Services without hours or a cost are allowed (Workbench only warns), e.g.
  when several people estimate their own services one after the other. Only
  touch the services you were asked about, never fill in or delete others.

Only for a completely new version of the offer, replace it entirely (as long
as nothing has been logged on its services yet), again with the user's
explicit approval:

    wb offers show <offer_id> --json
    wb offers replace <offer_id> <scratchpad>/offer.yaml --dry-run
    wb offers replace <offer_id> <scratchpad>/offer.yaml

`replace` swaps title, description, all services and the headings, so start
from the current offer and keep what wasn't asked to change (the headings of
`wb offers show --json` have positions like the services, `before` is the
index of the service which follows them).

If the reason for a revision isn't obvious from the offer itself (a new
requirement, a changed estimate), offer to record it as a note on the
project with `wb notes create --project <project_id>`.
