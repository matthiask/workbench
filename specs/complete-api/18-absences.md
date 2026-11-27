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
