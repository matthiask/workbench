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

## Decided

- `patch_with_form()` stays PATCH only. Creating needs no current values,
  and the create endpoints differ in their defaults (current user, today,
  the project of the path) more than they have in common; they keep
  calling `validate_form()` directly.

## Done (2026-11-27)

What the later packages need to know:

- `patch_with_form(form_class, instance, patch, request, *, out,
  ignore_warnings=(), dry_run=False, field_map=None, form_kwargs=None)`
  returns `out(saved_instance)`, computed before a dry run is rolled back.
  `patch` is the request body (unset fields are left alone) or a dict;
  null empties a field and the form decides. `field_map` values are a form
  field name, a converter (`active_user`, `api_key("offer_status")`,
  `object_pk(queryset)`, or any callable raising Django's
  `ValidationError`) or `(name, converter)`. Cross-field rules go into the
  patch dict before the call (see `project_update`).
  Since package 03 it refuses patched fields which the bound form disables
  or doesn't have (unless empty), and passes `ignore_warnings` to the form
  like the web interface's checkbox (`should_ignore_warnings()`).
- `delete_with_form(instance, request, *, loc, delete_form_class=None,
  data=None, fields=None, ignore_warnings=(), dry_run)`: delete forms have
  warnings too (`release-logged-services`, `release-down-payments`,
  `release-projects`), so it takes `ignore_warnings`. `loc` locates the
  refusals of `allow_delete()`. Serialize the instance first: deleting
  sets its PK to `None`, also in rolled back dry runs. Consequences which
  the web interface shows after deleting are in `instance.delete_warnings`
  (invoice services).
- All warnings had codes already (`code` is a required keyword of
  `add_warning()`); the test checks they're kebab-case literals.
- The coverage test lists the web views by URL name: `API_ROUTES` (the
  comments name packages which complete a route), `NOT_IN_API` (shrink it)
  and `WRITING_FUNCTION_VIEWS` (function views aren't found by class).
- `PATCH /api/projects/{id}/` with `"owned_by": null` is now the form's
  "required" error instead of being ignored.
