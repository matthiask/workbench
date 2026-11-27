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
