---
name: workbench-planning
description: Plan a Workbench project (milestones and planned work per person and week) from its offers and a timeline using the `wb` CLI, change existing planned work (e.g. make provisional work definitive once a deal is won, move or remove it), or look at the planning and the capacity of people and teams. Use when the user wants to plan, schedule, reschedule or staff a project in Workbench, or asks who has time when.
---

# Planning Workbench projects

The `wb` CLI talks to Workbench (see `wb --help`). If `wb` isn't installed or
configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`. Looking at the planning works with `--read` too;
if `wb` answers that the token only allows reading, ask the user to log in
with `--write` instead of working around it.

## Looking at the planning

    wb planning export --project <project_id>           # The whole planning of a project
    wb planning export --team "<team>" --period this-quarter
    wb planning export --user <short name> --period next-month
    wb planning export --project <project_id> --csv > <scratchpad>/planning.csv

With users or a team, the table shows the free capacity per person and week
(hours not planned yet, less absences and holidays).

## Planning a project

### 1. Find the project and get the context

    wb projects search <terms>
    wb planning context <project_id> > <scratchpad>/context.json

The context contains the project, its offers with their services, the people
(short names and planning hours per day), their absences, the existing
milestones and planned work, and `import_schema`, the exact JSON schema of
the import. Check everyone's capacity in the weeks in question:

    wb planning export --team "<team>" --since <first monday> --until <last day>

### 2. Draft the plan

Ask the user for what isn't in the offers: the timeline, fixed dates and who
does what. Then write the plan as YAML to the scratchpad, e.g.
`<scratchpad>/plan.yaml`, following `import_schema`:

- Weeks are given by their Monday (YYYY-MM-DD) and don't have to be
  consecutive.
- `planned_hours` is the total over all weeks of an entry, not per week.
- Respect each person's planning hours per day and their absences. People
  also work on other projects: don't plan anyone fully, check the capacity.
- Only use the listed people (by short name), service types and offers (by
  code). Planned work references new milestones by their key and existing
  ones by their ID.
- New entries have no `id`. To change existing milestones or planned work,
  include them with their `id` from the context and only the fields to
  change; to remove them, list their IDs in `delete_milestones` or
  `delete_planned_work`. Nothing else is changed or deleted.
- Estimate the hours from the offers' services, they should add up to the
  offered hours.
- Mark work as provisional (`is_provisional: true`) unless the user says it's
  definitive.

### 3. Review and import

Show the plan as a table (person, work, weeks, hours) with the totals per
person and week, and list your assumptions. Then validate it:

    wb planning import <project_id> <scratchpad>/plan.yaml --dry-run

Fix the errors and look at the warnings, e.g. work planned in or after the
week of its milestone. Check the capacity yourself with `wb planning export`
(the import doesn't). Import only after the user explicitly approves:

    wb planning import <project_id> <scratchpad>/plan.yaml

## Changing single planned work

Find the IDs with `wb planning context <project_id>` or `wb planning export
--project <project_id>`. Show the change and use `--dry-run` first, change
only after the user approves:

    wb planning work update <id> --definitive              # The customer decided
    wb planning work update <id> --week 2026-11-02 --week 2026-11-09 --hours 12
    wb planning work update <id> --user <short name> --clear-milestone
    wb planning work add <project_id> --title "Concept" --user <short name> \
        --service-type "<service type>" --week <monday> --hours 8
    wb planning work delete <id>

`--week` takes any day of a week and can be repeated, giving `--week`
replaces all weeks. New work is provisional unless `--definitive` is given.

When a deal is won or lost (see the workbench-deals skill), look for
provisional planned work on the offers related to the deal and offer to make
it definitive or to delete it.
