# Workbench CLI

The `wb` program talks to the Workbench JSON API. Install it with
[uv](https://docs.astral.sh/uv/):

    uv tool install "git+ssh://git@github.com/matthiask/workbench.git#subdirectory=cli"

or, from a local checkout:

    uv tool install --editable ./cli

Create a personal API token in Workbench ("API tokens" in the user menu) and
log in:

    wb login https://workbench.feinheit.ch

Check it with `wb whoami`. The URL and the token are stored in `~/.config/workbench.toml`. The
`WORKBENCH_URL` and `WORKBENCH_TOKEN` environment variables take precedence.

## Creating offers

Find the project:

    wb projects search relaunch
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

Offers in preparation can be replaced as long as no hours or costs have been
logged on their services:

    wb offers list 1234
    wb offers show 5678
    wb offers replace 5678 offer.yaml --dry-run
    wb offers replace 5678 offer.yaml

All commands which output data accept `--json`.

## Planning

Like offers: Fetch the context (offers, people, absences, existing milestones
and planned work, and the JSON schema of the import), let an LLM write the
plan, validate it and import it:

    wb planning context 1234 > context.json
    wb planning import 1234 plan.yaml --dry-run
    wb planning import 1234 plan.yaml

Importing only adds milestones and planned work, it never changes or removes
existing entries.

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

## Claude Code skill

`skills/workbench-offer/` contains a [Claude Code](https://claude.com/claude-code)
skill which turns a specification into an offer using `wb`: it finds the
project, fetches the context, drafts the offer, reviews it with you, validates
it with `--dry-run` and only creates it after your approval. Link it into your
personal skills to use it in any directory:

    ln -sfn "$PWD/cli/skills/workbench-offer" ~/.claude/skills/workbench-offer
