# 13 Planning: milestones and external work

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`planning_milestone_create|update|delete` → `MilestoneForm`;
`planning_externalwork_create|update|delete` → `ExternalWorkForm`.
Milestones are only written by the planning import today; external work
isn't in the API at all.

## API

`POST /api/projects/{id}/planning/milestones/`,
`PATCH`/`DELETE /api/planning/milestones/{id}/`; the same for
`external-work`. Include external work in `planning/export` and the
context if it isn't there yet.

## `wb`

`wb planning milestones create|update|delete`,
`wb planning external-work create|update|delete`.

## Done (2026-11-27)

- `POST /api/projects/{id}/planning/milestones/`, `PATCH`/`DELETE
  /api/planning/milestones/{id}/`, the same for `external-work` (path
  parameter `work_id`). All take `dry_run`, writes take `ignore_warnings`
  (`work-after-milestone`, `weeks-after-milestone`). Writes go through
  `MilestoneForm` and `ExternalWorkForm` with `patch_with_form()`, also
  for creating: an unsaved instance of the project gives the form's
  defaults (0 hours, the customer as provider, this week), so the form
  decides everything (closed projects, phase after the milestone, the
  color swatches, milestones of the project only, the form's range of
  weeks). The forms are decorated with `add_prefix("modal")`, the API uses
  the undecorated classes (`__wrapped__`); no form changes.
- External work fields: `provided_by` (organization ID), `service_type`
  (title, like planned work), `milestone` (ID), `weeks` (any day, stored
  as Mondays), `notes`, `title`.
- Responses are the `ImportResult` of the planned work endpoints, which
  got `external_work` and `deleted_external_work` (empty by default) and a
  `color` for milestones; additive, the import's output only gains fields.
  External work there has `provided_by` (name) and `provided_by_id` like
  `milestone`/`milestone_id`, not a nested organization. New objects have
  no ID with `dry_run`.
- `planning/export` had external work already; the planning context now
  lists it too (`external_work`: provider by name, milestone by ID). The
  import doesn't write external work.
- `wb planning milestones create PROJECT TITLE --date ... [--phase-starts-on
  --hours --color]`, `update ID [--title ... --clear-phase-starts-on
  --clear-color]`, `delete ID`; `wb planning external-work create PROJECT
  TITLE [--provided-by --service-type --milestone --week... --notes]`,
  `update ID [... --clear-service-type --clear-milestone]`, `delete ID`.
  Verb `create` as in the spec (planned work uses `add`).
