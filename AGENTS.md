# Running tests

Use `./runtests.sh` to run the full test suite. Accepts an optional module argument:

```
./runtests.sh
./runtests.sh workbench.projects.test_projects
```

The tests need the local PostgreSQL container: `podman start local_postgres_1`.

# Screenshots

The dev server (`:8000`) needs a login. Sessions are signed cookies, so log in
with `Client().force_login(user)` in `./manage.py shell` and pass
`client.cookies["sessionid"].value` to a browser, e.g. Playwright through
`uv run --with playwright python script.py` (the browsers are installed).
Hide the debug toolbar with `localStorage.setItem('djdt.show', 'false')` in an
init script; removing its elements breaks its JavaScript. The timer keeps its
activities in local storage, fresh browser contexts start empty.

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
  checked before the session because session auth requires a CSRF token, see
  `user_auth()` in `workbench/accounts/api_auth.py`). Tokens expire after
  `API_TOKEN_LIFETIME`; `wb login` gets a new one through `/cli-login/` in the
  browser, which posts it to a server the CLI runs on a local port. Tokens
  are created with an explicit `access` (read only or read and write, no
  default); read only tokens are rejected for everything but GET requests. Endpoints require the
  same features as the web interface: `user_auth(feature=FEATURES.CONTROLLING)`
  on the router or the endpoint, checked before the request is validated. The
  reporting router uses the static bearer token (`ReportingToken` in
  `workbench/reporting/api.py`). Routes end with a slash. The Django test
  client skips CSRF checks, use `Client(enforce_csrf_checks=True)` to test
  them.
- The `wb` command line interface lives in `cli/` (separate package, installed
  with `uv tool install`). It is a thin client of the JSON API, keep the logic
  on the server. Commands follow `wb <noun> <verb>`, e.g. `wb projects search`.
  Verbs: `search` (optional terms plus filters like `--project`, `--customer`,
  `--owned-by`; the API supports the same filters), `show ID`, `create`.
  Nouns without a verb show the most common list (`invoke_without_command`):
  `wb projects` your open projects, `wb hours` your hours of this week, `wb
  offers`/`invoices`/`deals` yours which may need action (like `wb me`), `wb
  users`, `wb teams`, `wb auth` the installations; nouns which need a search
  term show the help. `wb search` searches everything like the search field
  of the web interface (`/api/search/`, sources shared with the web view in
  `workbench/search.py`).
  The package `cli/wb/` has one module per noun (`wb/offers.py`); `wb/core.py`
  has the configuration, requests, output helpers and options they share.
  `wb contacts search` finds both organizations and people, `wb organizations
  show` and `wb people show` show them. `wb people create` is mostly fed by
  LLMs, so the API rejects duplicate names and email addresses (the web
  interface doesn't). Shared validation helpers for the APIs are in
  `workbench/tools/api.py`, also `DateRangeFilter` (`period` like `2026-Q3` or
  `last-month`, `since`, `until`) with `date_range()` and `filter_date_range()`
  for reports and searches, and `UsersFilter` with `filter_users()` for
  reports. Cutoff dates are called `date`. Reports live at
  `/api/reports/<name>/` with the names of `wb reports`; key data and cash
  data are also served at their old URLs (`/api/key-data/`, `/api/cash-data/`,
  hidden from the schema) for integrations. Responses have schemas and decimals are
  strings everywhere (`Amount`, `Hours`, `Days` and `Percentage` in
  `workbench/tools/api.py` round computed values), except key data and cash
  data which use `jsonable()` for the integrations.
  Search endpoints use ninja's `@paginate` (limit and offset, 100 per page,
  at most 10000; responses are `{items, count}`) and return a `Serialized`
  queryset from `workbench/tools/api.py` so that only the page is serialized,
  ordered unambiguously (add `pk`). `TotalsPagination` adds totals of all
  matches, e.g. the hours of the logbook search.
  Report endpoints require the same feature as the web view (squeeze:
  productivity, deals: deals, most others: controlling); the static
  `ReportingToken` only grants key data and cash data.
  Organizations (e.g. customers) and projects are nested with their ID, name
  or code and URL (`organization_out()` in `workbench/contacts/api.py`,
  `project_summary()` in `workbench/projects/api.py`) so the CLI can link
  them.
  Bump the version in `cli/pyproject.toml` when changing the CLI: the server
  reads it and tells users of older versions to upgrade. Raise `MINIMUM` in
  `workbench/cli_version.py` when older versions don't work anymore.
  `workbench/test_cli.py` runs the real CLI commands against the API (requests
  go through Django's test client); add a test there for new commands. The CLI
  is installed with the project's dev dependencies, not in the container.
  Hours are not logged through the CLI on purpose: the warnings of the web
  interface's logbook forms are useful. The offers API (`workbench/offers/api.py`) only changes offers
  in preparation: create, replace, update and add, update, delete and reorder
  single services, all with the rules of `_apply_service()`. Service types only suggest the effort type
  and the hourly rate, both can be set freely.
- Timestamps may have a project and a service which pre-fill the logbook form
  of their slice (`wb ts start -p profond`). The API accepts a project ID or a
  part of the code, title or customer of one of the user's open pinned
  projects (`_project()` in `workbench/timer/api.py`).
- Short names (`User._short_name`) are unique when case folding, unless blank.
  APIs identify people by their short name and match it case-insensitively.
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
- `LoggedHours.invoiced_hours` (optional) is what the work is worth if that
  is more than the time spent (the form warns about lower values). Value and
  invoice logged work with `INVOICED_HOURS`
  (`Coalesce("invoiced_hours", "hours")` in `workbench/logbook/models.py`,
  annotate querysets with it); everything about
  time (utilization, productivity, planning, squeeze's hours, budgets in hours)
  uses `hours`.
- Sickness absences are health data ("besonders schützenswerte
  Personendaten"): only the absent person and users with
  `PERSONNEL_ADMINISTRATION` see their reason and description
  (`Absence.details_visible_to()`, `reason_for()`, `description_for()`, the
  `absences` template filters; `visible_absences()` leaves them out of
  searches and reason filters). Others see an "absence". `Absence.__str__`
  contains neither. Planning and its mails use `public_text()`. The annual
  working time report of others requires the feature, the history shows
  reasons and descriptions only with it, and `clear_sickness_descriptions()`
  (fairy tasks) clears descriptions and history after three years, like
  the audit log pruning of absences.
  Descriptions of absences are optional. Paid leave counts right away but
  needs a confirmation by someone with `PERSONNEL_ADMINISTRATION`
  (`Absence.needs_confirmation`, `update_confirmation()` in the form,
  `Absence.objects.unconfirmed()`, listed under "needs action").
- Contacts unused for five years are archived (`archive_unused_contacts()` in
  `workbench/contacts/tasks.py`, fairy tasks). Reverse relations are
  discovered with `_meta.get_fields()`; `_recent()` says which related
  objects count as recent use, contacts referenced by models missing there
  are always kept (a test lists all relations). Membership in groups which
  aren't archived keeps contacts, so do edits in the audit log.
- Planning does not care about `Service.is_optional`; planned work has its own
  `is_provisional` flag for definitive vs. provisional work.
- Page layout (see `projects/project_detail.html` and the contacts detail
  pages): `.wb-page-header` with the title, `.wb-meta` below it and
  `.wb-page-actions` (one primary action, `btn-quiet` buttons, a "New"
  dropdown for related objects, a kebab `btn-icon` menu for rare or
  destructive actions; no button bars at the bottom). Key figures are
  `.wb-stats` tiles, label/value pairs `dl.wb-fields`, related lists
  `list-group-flush` in cards. List pages override the `rows` block of
  `generic/object_list.html` with `.wb-row` items. Reports extend
  `reporting/report.html` (blocks `heading`, `actions`, `filters`,
  `report`) and put tables in `section.card.wb-table-card`, without zebra
  stripes; totals rows get `.wb-total-row`. Styles live in
  `workbench/static/workbench/main.scss` and must work in light and dark
  mode (`data-bs-theme`).
- Charts are server-side SVG, not chart.js: `bar_chart()` in
  `workbench/tools/charts.py` rendered with `charts/bar_chart.html`, colors
  from `.wb-series-1` to `-8`, `-muted` and `-neutral` (colors with a
  meaning: good green/blue, bad orange, neutral grey).
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
