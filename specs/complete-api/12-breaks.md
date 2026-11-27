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

## Done (2026-11-27)

- `GET /api/logbook/breaks/` lists **everyone's** breaks like the web
  list and like `GET /api/logbook/hours/` (filters `user`, `q` on the
  description, `period`/`since`/`until` on the day), newest first, with
  `total_minutes` of all matches. "Own breaks by default" is the CLI's
  default: `wb breaks` without a command lists your breaks of this week,
  like `wb hours`.
- Breaks are output with `day`, `starts_at`/`ends_at` (local datetimes,
  like the timer's slices) and `minutes`; the input takes the form's
  fields `day` (default today), `starts_at` and `ends_at` (times of the
  day) and `description`.
- `POST` creates breaks of the current user only (like the form);
  `PATCH`/`DELETE` refuse others' breaks with the web interface's message
  (`Break.allow_update`, which is also `allow_delete`), located at
  `["path", "break_id"]`. Patching only `day` keeps the times.
- The timer's query parameters (`timestamp`, `detected_ends_at`) are
  ignored like for logged hours: the API links no timestamps.
- Bug fixed in the web interface too: `BreakForm` never ran the model's
  validation of the times (they aren't model fields of the form), so
  breaks ending before they began were saved. It now refuses them.
- `wb breaks [search]|create STARTS_AT ENDS_AT [DESCRIPTION]|update ID|
  delete ID`; the workbench-logbook skill logs missing breaks instead of
  ignoring `take-a-break`.
