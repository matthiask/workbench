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
