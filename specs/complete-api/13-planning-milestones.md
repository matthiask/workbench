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
