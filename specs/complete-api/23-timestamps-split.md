# 23 Timestamps: split

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`split_timestamp` (`workbench/timer/urls.py`).

## API

`POST /api/timestamps/{id}/split/` with what the view takes.

## `wb`

`wb timestamps split`.

## Done (2026-11-27)

- `POST /api/timestamps/{timestamp}/split/` `{parts}` with the query
  parameters `day` and `dry_run`. `{timestamp}` is a code (T1, T2, ... of
  `day`, today by default) or an ID like for `DELETE
  /api/timestamps/{timestamp}/` (the lookup is shared now). Only the own
  timestamps (others are 404). Returns the parts' timestamps
  (`list[TimestampOut]`, chronological, the original timestamp last),
  each with its slice; codes are renumbered.
- `SplitTimestampForm` validates `parts` (at least 2, at most the slice's
  tenths of an hour) and now does the splitting (`save(timestamp)`) for
  the web view and the API; the web interface behaves as before.
- Deviation: the web view answers 404 for timestamps linked to logged
  hours or a break and a message for slices which can't be split (no
  start, no duration); the API refuses both with 422 "This timestamp
  cannot be split." at `["path", "timestamp"]`, clearer for callers.
- No `ignore_warnings`: the form has no warnings (like the notes
  endpoints, `wb` uses `change_options(warnings=False)`). The other
  timestamp writes (create, delete) still have no `dry_run`, left alone.
- `wb timestamps split TIMESTAMP PARTS [--day] [--dry-run] [--json]`
  (also `wb ts split`): prints the parts, then the day's renumbered list
  (dry run: the parts only). Mentioned in the `workbench-logbook` skill.
