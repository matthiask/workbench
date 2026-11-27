# 00 Groundwork

Part of [a complete API and `wb`](README.md); read the README's
decisions first.

## Goal

Shared helpers so that every other package is mostly declarative, and a
test that keeps new web actions from opening new gaps.

## Work

- `patch_with_form(form_class, instance, patch, request, *,
  ignore_warnings, dry_run, field_map=None, form_kwargs=None)` in
  `workbench/tools/api.py`: the patched fields (unset ones excluded) on top
  of `form_data()`, API names mapped to form fields (short names to user
  PKs of **active** users, `api_keys` keys to numeric statuses, IDs or
  codes to PKs), `validate_form()`, save in a transaction, roll back for
  dry runs. Errors located at `["body", "data", <api field>]`.
  `PATCH /api/projects/{id}/` and `PATCH /api/deals/{id}/` are the models;
  refactor one of them onto the helper to prove it fits.
- `delete_with_form(instance, request, *, delete_form_class=None,
  data=None, dry_run)`: `check_allow_delete()`, then the view's delete
  form if there is one (its fields as parameters), then the deletion,
  rolled back for dry runs. Mirror `generic.DeleteView`.
- `wb` helpers in `cli/wb/core.py`: a decorator adding `--dry-run`,
  `--ignore-warning` and `--json` to update and delete commands, and a
  shared confirmation-free delete echo.
- Warning codes: a test which finds every `add_warning()` without
  `code=` in forms used by the API (or all forms, simpler) and fails; add
  the missing codes.
- Coverage test in `workbench/test_api_schema.py`: every URL whose view is
  an `UpdateView`, `DeleteView`, `CreateView` or one of the function views
  writing data has an API route, or is listed in an explicit
  `NOT_IN_API = {url_name: reason}`. Start the list with everything the
  other packages will remove, so the test passes now and each package
  shrinks it.

## Questions

- Should `patch_with_form()` also cover creating (POST) or stay PATCH only?
