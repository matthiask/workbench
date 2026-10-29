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
- Shared helpers for reports: `Invoice.objects.outstanding(on=date)` for
  invoices open on a cutoff date; `sum_of(queryset, field=...)`,
  `sum_by(queryset, key=..., field=...)` (e.g. `key="service__project"`),
  `sum_by_month(queryset, date_field=..., field=...)` and
  `effort_cost_by_project(logged_hours)` in `workbench/reporting/utils.py`
  for totals (pass `default=Z1` for hours; everything after the queryset is
  keyword-only);
  `month_range(day)` and `last_month_range()` in
  `workbench/tools/validation.py`; `gross_margin_components(projects)`
  and `hours_components(projects)` in `workbench/reporting/squeeze.py` for
  offered/projected/invoiced gross margin and offered/logged hours;
  `jsonable()` in `workbench/reporting/api.py` for the token-authenticated
  JSON APIs. Prefer calling utilities over adding mixins or base classes.
- The JSON APIs use django-ninja (`workbench/api.py`, mounted at `/api/`) with
  one router per app. Endpoints authenticate with the user's session by
  default, or with personal API tokens (`APIToken`, sent as bearer token,
  checked before the session because session auth requires a CSRF token); the
  reporting router uses the static bearer token (`ReportingToken` in
  `workbench/reporting/api.py`). Routes end with a slash. The Django test
  client skips CSRF checks, use `Client(enforce_csrf_checks=True)` to test
  them.
- The `wb` command line interface lives in `cli/` (separate package, installed
  with `uv tool install`). It is a thin client of the JSON API, keep the logic
  on the server. Commands follow `wb <noun> <verb>`, e.g. `wb projects search`.
  Hours are not logged through the CLI on purpose: the warnings of the web
  interface's logbook forms are useful. The offers API (`workbench/offers/api.py`) only creates and
  replaces offers in preparation. Service types only suggest the effort type
  and the hourly rate, both can be set freely.
- Short names (`User._short_name`) are unique unless blank. APIs identify
  people by their short name.
- The planning import prompt is pasted into external LLMs. Keep personal data
  out of it: people are identified by their short name only (no email
  addresses or full names, see `plannable_users()` in
  `workbench/planning/api.py`), and absences have no reason.
- Offered amounts and offered hours only count for open projects; for closed
  projects the invoiced amount and the logged hours are ground truth.
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
  would count them twice. This applies to squeeze and to the invoiced gross
  margin which uses up projected invoices alike.
- Projected invoices (`ProjectedInvoice.gross_margin`) are gross margin, third
  party costs are not included. Invoiced gross margin uses up a project's
  oldest projections first. Projections which haven't been invoiced in time
  stay in their original month (key data report and cash data API alike); the
  cash data API reports their sum separately as
  `planned_invoicing_overdue_excl_tax` since its months start at the cutoff
  date.
- In the cash data API, `accepted_offers_not_invoiced.total_excl_tax` is
  revenue, but `not_in_planned_invoicing_excl_tax` is gross margin because it
  complements planned invoicing. Never subtract gross margin from revenue.
  Figures based on projects (accruals, planned invoicing, offers) leave out
  internal projects; open invoices include all invoices. `work_not_invoiced`
  is the positive side of the project budget statistics' delta (logged work
  valued at effort rates), `accruals` the negative side.
- Planning does not care about `Service.is_optional`; planned work has its own
  `is_provisional` flag for definitive vs. provisional work.
- Pre-commit hooks (via `prek`, not `pre-commit`) run on commit, ruff included, and auto-fix formatting. If a commit fails due to formatting, re-stage the auto-fixed files and commit again.
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
- Work on `main` directly, no feature branches. Fast-forward instead of
  creating merge commits whenever possible.
