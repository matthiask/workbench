# 14 Planning: batch update

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Goal

What a handover needs: "give all future planned work of X to Y". The
import works per project and can't do it.

## Web reference

`planning_batch_update` (`workbench/planning/views.py`) →
`PlannedWorkBatchForm`: selected work, `move_by_weeks`, `assign_to`
(user), `project`, `provisional`, `delete`. Called per project or per
offer (`kind`).

## API

`POST /api/planning/work/batch/` `{work: [ids], move_by_weeks,
assign_to, project, provisional, delete}`. Allow selecting work across
projects (e.g. all of one user) if the form can cope; otherwise call it
per project and let the CLI loop.

## `wb`

`wb planning work batch --user ub --since 2026-12-01 --assign-to aha`
(selects through the export filters, then calls the batch endpoint),
`--move-by-weeks`, `--provisional/--definitive`, `--delete`.

## Done (2026-11-27)

- `POST /api/planning/work/batch/` with `{work, move_by_weeks,
  assign_to, project, provisional, delete}`, `dry_run` and
  `ignore_warnings` (the form has no warnings yet). It goes through
  `PlannedWorkBatchForm` unchanged: its queryset of selectable work is
  `PlannedWork.objects.filter(pk__in=<the given IDs>)` instead of the
  work of one project, so the selection may span projects (every user
  may change all planned work, like in the web interface). Unknown IDs
  are the form's "Select a valid choice" error. `assign_to` is
  converted with `active_user`, `project` (ID or code) with
  `object_pk(Project.objects.all())` so that closed projects get the
  form's error.
- The response is the `ImportResult` of the other planned work
  endpoints: the changed work in `planned_work`, deleted IDs in
  `deleted_planned_work`.
- `wb planning work batch`: the target project is `--move-to-project`
  (the form's label), because `--project` selects like in `wb planning
  export`. Without `--period` or `--until` it selects the work from
  `--since` (default today) for ten years, not the export's twelve
  weeks. Filters and `--work` exclude each other; `--delete` with
  changes, nothing to change or no filter are refused by the CLI.
- Like in the web interface, work overlapping the start of the period
  changes as a whole (also its past weeks); the CLI says how many
  selected entries have earlier weeks. Splitting them is up to the user.
- The help pages (`docs/planning*.md`) mention the command.
