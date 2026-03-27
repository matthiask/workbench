# Running tests

Use `./runtests.sh` to run the full test suite. Accepts an optional module argument:

```
./runtests.sh
./runtests.sh workbench.projects.test_projects
```

# Translations

Update and compile the translation catalog with:

```
fl mm   # makemessages
fl cm   # compilemessages
```

Edit `conf/locale/de/LC_MESSAGES/django.po` manually. Remove the `#, fuzzy` flag before any new entry or it won't be used.

# Conventions

- `grouped_services` (on `Project`) returns a **dict**, not an object — use `gs["key"]` not `gs.key`. Template access works with dot notation automatically.
- `Decimal` zero constants: `Z1 = Decimal("0.0")` for hours, `Z2 = Decimal("0.00")` for money (imported from `workbench.tools.formats`).
- `Offer.is_accepted` checks `status == ACCEPTED`. Use this (not `not is_declined`) when computing accepted-offer totals.
- `project_gross_margin(project)` in `workbench/reporting/squeeze.py` computes single-project profitability (gross margin, rate, offered/projected/invoiced breakdown). Use this instead of duplicating squeeze logic.
- Pre-commit hooks run ruff and auto-fix formatting. If a commit fails due to formatting, re-stage the auto-fixed files and commit again.
- Template arithmetic is not supported in Django `{% if %}` tags — precompute derived values (thresholds, flags) in the view instead.
