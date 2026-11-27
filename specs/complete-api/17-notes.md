# 17 Notes

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Web reference

`notes_note_update`, `notes_note_delete` → `NoteForm`.

## API

`PATCH`/`DELETE /api/notes/{id}/` (also `GET` if missing).

## `wb`

`wb notes update|delete`.

## Done (2026-11-27)

- `GET`, `PATCH` and `DELETE /api/notes/{id}/`. Like the web interface
  (`Note.allow_update()`/`allow_delete()`), everyone who may see the notes
  of the object's type may change or delete a note, not only its author.
  Notes on objects the user may not see and notes of deleted objects
  aren't found (404, like the list leaves them out) instead of the web
  interface's "not permitted" message.
- `PATCH` changes `title` and `description` through `NoteForm`; notes
  aren't moved to another object (the form has no such field for existing
  notes). `NoteForm` has no warnings, so neither endpoint takes
  `ignore_warnings` (and `wb notes update|delete` no `--ignore-warning`).
- Nothing is mailed; changes by others show up in the owner's next daily
  digest (audit log), like edits in the web interface.
- `wb notes show|update|delete ID`; `update --title --description` (`-`
  reads stdin), `--dry-run`, `--json`. No form changes.
