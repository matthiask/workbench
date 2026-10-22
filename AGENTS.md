# Running tests

Use `./runtests.sh` to run the full test suite. Accepts an optional module argument:

```
./runtests.sh
./runtests.sh workbench.projects.test_projects
```

The tests need the local PostgreSQL container: `podman start local_postgres_1`.

# Fixing bugs

1. Write a test which reproduces the bug.
2. Run it and make sure it fails, and fails for the right reason.
3. Simplify the test down to the essential behaviour.
4. Run it again and make sure it still fails.
5. Only then implement the fix and confirm the test passes.

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
- Profitability estimates (rates, gross margins) should rather underestimate
  than overestimate. When in doubt, count hours and leave out money.
  The overall rate counts all budgeted hours (also from offers not accepted
  yet); the rate based on accepted offers only their hours (offered or
  logged, whichever is higher). Hours logged on
  services which aren't budgeted (optional, declined) are added on top.
- Squeeze splits a project's gross margin between people by hours weighted
  with the service's hourly rate. Services without a rate or with a rate of
  0.00 (work paid elsewhere, e.g. by a package price) are weighted with
  `BASE_HOURLY_RATE`.
- Third party costs are deducted once: the larger of those on invoices and
  the logged ones (`third_party_costs()` in `workbench/reporting/squeeze.py`).
  Logged costs can't be linked to fixed amount invoices, so adding up both
  would count them twice.
- Planning does not care about `Service.is_optional`; planned work has its own
  `is_provisional` flag for definitive vs. provisional work.
- Pre-commit hooks run ruff and auto-fix formatting. If a commit fails due to formatting, re-stage the auto-fixed files and commit again.
- Template arithmetic is not supported in Django `{% if %}` tags — precompute derived values (thresholds, flags) in the view instead.
- Use `speckenv` to load `.env` files in standalone Python scripts: `from speckenv import read_speckenv; read_speckenv(Path(__file__).parent / ".env")`
- In templates, when you check a queryset for existence and then iterate it,
  bind it once with `{% with objects=obj.related.all %}` -- otherwise the
  attribute is evaluated (and the query run) twice.
- The "add issue to project" GitHub Actions workflow is duplicated across individual repos and should be consolidated into the org-level `.github` repo (org-level workflows apply to all repos). The cross-app parent warning workflow goes there too. See `specs/github-cost-allocation-report.md`.

# Committing

- Commit feature by feature: one self-contained change per commit, not a single
  batch commit at the end of a session.
- No attribution trailers in commit messages (no `Co-Authored-By:`, no
  "Generated with ..." footers).
- Commit messages are written in English.
