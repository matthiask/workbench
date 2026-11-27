# 19 Teams

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`accounts_team_create|update|delete` → `TeamForm`. The own profile
(`accounts_update`, `UserForm`) stays in the web interface.

## API

`POST /api/teams/`, `PATCH`/`DELETE /api/teams/{id}/`.

## `wb`

`wb teams create|update|delete`.

## Done (2026-11-27)

- Anyone may manage teams in the web interface (plain generic views, no
  feature), so the API requires nothing beyond a write token.
- `POST /api/teams/` (`name`, `members`), `PATCH /api/teams/{team_id}/`
  (`name`, `members` replaces them, `add_members`, `remove_members`) and
  `DELETE /api/teams/{team_id}/`, all with `dry_run`; no
  `ignore_warnings` (`TeamForm` has no warnings). Teams are given by ID or
  name (case-insensitive) like servers. Members are short names of active
  users, like the form's choices. Writes go through `TeamForm` with
  `patch_with_form()`, also for creating (an unsaved team).
- The API always submits the members: the web form only shows active
  members, so saving it drops members who left; `form_data()` would submit
  them and fail as invalid choices. The output listed only active members
  already, nothing visible changes.
- Form change (web too): `TeamForm` refuses names which exist already
  (case-insensitive), like `GroupForm` for group titles. The `team`
  filters (`Team.objects.get(name__iexact=...)`) crashed with two teams of
  the same name.
- `wb teams create NAME --member ...`, `wb teams update TEAM [--name
  --member ... --add-member ... --remove-member ...]`, `wb teams delete
  TEAM`. Changing teams deletes the cached team names for completing
  `--team` (`forget_completion_values()` in `cli/wb/core.py`); short names
  don't change, their cache stays.
- Names containing `/` can't be used in the path (Django's path
  converter), use the ID then.
