# 18 Absences

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`awt_absence_update`, `awt_absence_delete` (`ReportedDeleteView`) →
`AbsenceForm`. Sickness descriptions
are health data (`details_visible_to()`).

## API

`PATCH`/`DELETE /api/absences/{id}/`. Confirming paid leave
(`awt_absence_confirm`, `PERSONNEL_ADMINISTRATION`) stays in the web
interface.

## `wb`

`wb absences update|delete`.

## Done (2026-11-27)

- `PATCH /api/absences/{id}/` through `patch_with_form()` with
  `AbsenceForm.__wrapped__` (the form is wrapped by `@add_prefix("modal")`)
  and `without_query(request)` (the form takes initial values and
  `replaces` from the query string). `DELETE /api/absences/{id}/` through
  `delete_with_form()` (`ReportedDeleteView` has no delete form).
- Both check `Absence.allow_update` first (`allow_delete` is the same):
  the absent person, personnel administration, and on the same day
  whoever entered the absence; past years locked; corrections only for
  personnel administration. Refusals are located at
  `["path", "absence_id"]`. The web interface's `UpdateView` checks it in
  `dispatch()`, `patch_with_form()` doesn't, so the endpoint does.
- `user` is refused for others than personnel administration (the form
  disables it). Changing someone else's absence is the form's warning
  `absence-of-others`.
- Sickness descriptions: the responses of update and delete (also dry
  runs) use `description_for()` like `GET`. Changing the reason of a
  sickness absence with a description stays the form's error; its link
  to replacing the absence is stripped from the message (the API way:
  clear the description, or create a new absence and delete the old one).
- Deleting someone else's absence: `ReportedDeleteView` only shows a note
  on the confirmation page and sends nothing itself. The weekly mail to
  personnel administration (`changes_by_others_mails()`) reads the audit
  log, so API deletions are reported like web deletions (tested); that's
  the domain rule, nothing extra is needed and nothing is mailed right
  away. No warning code for deleting, like `DELETE /api/logbook/hours/`.
- `AbsenceOut.days` is `Days` now (two places), so dry runs show `2.00`
  instead of `2` like saved absences.
- `wb absences update ID` (`--starts-on`, `--ends-on`, `--single-day`,
  `--days`, `--reason`, `--description`, `--user`) and
  `wb absences delete ID`.
- Confirming paid leave stays in the web interface (`NOT_IN_API`).
- Open: `POST /api/absences/` requires `days > 0`, while the form allows
  negative days for working time corrections (personnel administration):
  an API-only restriction, left alone here.
