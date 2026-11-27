# 12 Breaks

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`logbook_break_create`, `_update`, `_delete` → `BreakForm`. Breaks count
for the working time; the timer creates them too.

## API

`GET`/`POST /api/logbook/breaks/`, `PATCH`/`DELETE
/api/logbook/breaks/{id}/`, own breaks by default like hours.

## `wb`

`wb breaks [list]|create|update|delete`.
