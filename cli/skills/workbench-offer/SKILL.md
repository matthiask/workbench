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
- Estimate hours realistically, rather a bit high than too low. Things the
  specification mentions as "maybe", "nice to have" or "later" become optional
  services.
- Licenses, hosting, stock images etc. are `cost`, with `third_party_costs`
  for what's passed on from third parties.
- Leave out `postal_address`; Workbench uses the project's contact.

## 4. Review with the user

Show the draft as a table (service, effort type, hours, rate, amount, optional)
with the totals, and list your assumptions and open questions. Then validate it
on the server, which also computes the totals:

    wb offers create <project_id> <scratchpad>/offer.yaml --dry-run

Fix any errors (they name the field, e.g. `services.2.hours`) and iterate
with the user until they're happy.

## 5. Create the offer

Only after the user explicitly approves:

    wb offers create <project_id> <scratchpad>/offer.yaml

Report the offer code and its URL. Remind the user that the offer is in
preparation and still has to be checked and sent in Workbench.

## Revising an offer

Offers in preparation are changed service by service. Look at the current
offer first; its table shows the IDs of the services:

    wb offers show <offer_id>

Change only what was asked, one command per change, each one first with
`--dry-run`:

    wb offers update <offer_id> --title "<title>" --description - < <scratchpad>/text.txt
    wb offers services add <offer_id> --title "<title>" --service-type "<type>" --hours 12 --after <service_id> --dry-run
    wb offers services add <offer_id> <scratchpad>/service.yaml --dry-run
    wb offers services update <offer_id> <service_id> --hours 20 --dry-run
    wb offers services update <offer_id> <service_id> <scratchpad>/service.yaml --dry-run
    wb offers services delete <offer_id> <service_id> --dry-run
    wb offers services reorder <offer_id> <service_id> <service_id> ... --dry-run

- `update` only sends the given fields, everything else stays as it is.
  `--clear-hours` and `--clear-cost` remove values, `--optional` and
  `--no-optional` switch whether a service counts towards the total.
- A service file contains a single service like in step 3 (`title`,
  `description`, `service_type`, `hours`, `cost`, ...); options override it.
  Use files for longer descriptions.
- Show the user how the change affects the totals (the dry run prints the
  whole offer) and run the command without `--dry-run` only after their
  explicit approval.
- Services with logged hours or costs can be changed but not deleted, and the
  last service of an offer can't be deleted.
- Services without hours or a cost are allowed (Workbench only warns), e.g.
  when several people estimate their own services one after the other. Only
  touch the services you were asked about, never fill in or delete others.

Only for a completely new version of the offer, replace it entirely (as long
as nothing has been logged on its services yet), again with the user's
explicit approval:

    wb offers show <offer_id> --json
    wb offers replace <offer_id> <scratchpad>/offer.yaml --dry-run
    wb offers replace <offer_id> <scratchpad>/offer.yaml

`replace` swaps title, description and all services, so start from the
current offer and keep what wasn't asked to change.
