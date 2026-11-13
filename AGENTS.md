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

# Verification rounds

From time to time (or when asked what we're missing), look for behaviour
the tests don't cover, above all scenarios combining features over time:
offers, services and their logged hours and costs, invoices (fixed amount,
services, down payments, credits, recurring), projected invoices, archiving,
closing projects and deals, the reports and key figures (`docs/metrics.md`),
absences and the annual working time, planning, contacts (merging,
archiving, groups), the audit log, the API and `wb`.

1. A fresh agent reads this file, `docs/metrics.md`, the specs in
   `specs/`, the code and the tests, read-only and without our hypotheses.
   Tell it what's covered already (the tests, `git log --grep=Test:`, the
   findings of earlier rounds in `specs/verification.md`) and to separate
   verified bugs (shown with a throwaway test it deletes afterwards) from
   untested risks. Split large areas between several agents.
2. Check its findings against the code before relying on them.
3. Ask the user where the behaviour is a decision rather than a bug.
4. Fix bugs as above (failing test first), one commit each, docs included
   (`docs/metrics.md` for computations). Tests go into the app's tests,
   API and CLI round trips into `workbench/test_cli.py`.
5. Keep the open findings in `specs/verification.md` until they're done,
   so that the next session continues there.

# Translations

Update and compile the translation catalog with:

```
fl mm   # makemessages
fl cm   # compilemessages
```

Edit `conf/locale/de/LC_MESSAGES/django.po` manually. Remove the `#, fuzzy` flag before any new entry or it won't be used.

# Conventions

## Code

- `grouped_services` (on `Project`) returns a **dict**: `gs["key"]` in
  Python, dot notation works in templates.
- `Z1 = Decimal("0.0")` for hours, `Z2 = Decimal("0.00")` for money
  (`workbench.tools.formats`).
- `Offer.is_accepted` (`status == ACCEPTED`), not `not is_declined`, for
  accepted-offer totals.
- Report helpers, prefer calling them over adding mixins or base classes:
  `Invoice.objects.outstanding(on=date)`; `sum_of()`, `sum_by()`,
  `sum_by_month()` and `effort_cost_by_project()` in
  `workbench/reporting/utils.py` (keyword-only after the queryset, pass
  `default=Z1` for hours); `month_range()` and `last_month_range()` in
  `workbench/tools/validation.py`; `gross_margin_components()`,
  `hours_components()` and `project_gross_margin()` in
  `workbench/reporting/squeeze.py` (don't duplicate squeeze logic).
- Template arithmetic isn't supported in `{% if %}`: precompute in the view.
  Bind querysets which are checked and iterated once with `{% with %}`.
- Pre-commit hooks run through `prek` (not `pre-commit`) and auto-fix
  formatting; re-stage the fixed files and commit again.
- Standalone scripts load `.env` with `speckenv.read_speckenv()`.

## Web interface

- Page layout like `projects/project_detail.html`: `.wb-page-header`,
  `.wb-meta`, `.wb-page-actions` (one primary action, `btn-quiet` buttons, a
  "New" dropdown, a kebab menu for rare or destructive actions, no button
  bars at the bottom), `.wb-stats` tiles, `dl.wb-fields`, related lists as
  `list-group-flush` in cards. List pages override the `rows` block of
  `generic/object_list.html` with `.wb-row` items. Reports extend
  `reporting/report.html`, tables in `section.card.wb-table-card` without
  zebra stripes, totals rows `.wb-total-row`. Styles in
  `workbench/static/workbench/main.scss`, light and dark mode.
- Collapsed content uses `hidden="until-found"` (not `.collapse` or line
  clamps) so the browser's search finds it; long descriptions use
  `{% clamped %}`. Textareas grow with their content, `.wb-no-autogrow`
  opts out.
- Charts are server-side SVG (`bar_chart()` in `workbench/tools/charts.py`,
  `charts/bar_chart.html`), colors `.wb-series-1`…`-8`, `-muted`,
  `-neutral` (good green/blue, bad orange, neutral grey).

## API

- django-ninja (`workbench/api.py`, `/api/`), one router per app, routes end
  with a slash. Personal API tokens (bearer, read only or read and write)
  are checked before the session (`user_auth()` in
  `workbench/accounts/api_auth.py`); endpoints require the same features as
  the web views (`user_auth(feature=...)`). The static `ReportingToken` only
  grants key data and cash data. The test client skips CSRF checks, use
  `Client(enforce_csrf_checks=True)` to test them.
- Request bodies derive from `InputSchema` (`workbench/tools/api.py`) and
  reject unknown fields, so data under a wrong key isn't lost silently.
- Web forms validate the API too (`validate_form()`): their warnings are
  errors carrying a code, ignored only when listed in `ignore_warnings`.
- Decimals are strings (`Amount`, `Hours`, `Days`, `Percentage`), except
  key data and cash data (`jsonable()`, used by integrations, also at their
  old URLs). Numeric statuses and probabilities are output and accepted as
  stable keys (`workbench/api_keys.py`), choices get a localized `*_label`,
  never display strings; `/api/choices/` lists them.
- Errors are `{"detail": [{"loc", "msg", "code"}]}`, also for `HttpError`
  and 404; only the upgrade notice for outdated CLIs stays plain.
- Schema class names are unique across routers, query parameters have
  descriptions (both checked by `workbench/test_api_schema.py`).
- Searches use `@paginate` with a `Serialized` queryset ordered
  unambiguously (add `pk`). Date filters use `DateRangeFilter`, user filters
  `UsersFilter`; cutoff dates are called `date`. Short names identify users,
  case-insensitively; unknown ones are rejected (`user_by_short_name()`).
- Organizations and projects are nested with ID, name or code and URL
  (`organization_out()`, `project_summary()`).
- Messages added during API requests are dropped
  (`api_messages_middleware`).
- On purpose: hours aren't logged through the API (the logbook form's
  warnings matter); dates of birth aren't in the API; creating people
  rejects duplicates (mostly fed by LLMs).

## `wb` command line interface

- Lives in `cli/` (own package, one module per noun, shared helpers in
  `wb/core.py`). A thin client: keep the logic on the server.
- `wb <noun> <verb>`: `search` (terms and filters, `--include-closed` etc.,
  `include_*` in the API), `show ID` (ID or code, `by_id_or_code()`),
  `create`, `update`. Nouns without a verb show the most common list.
- New commands get a test in `workbench/test_cli.py` (real commands against
  the API through the test client).
- Bump the version in `cli/pyproject.toml` when changing the CLI (once per
  batch); raise `MINIMUM` in `workbench/cli_version.py` when older versions
  break. The CLI needs the server's Python (`UPGRADE` has `--python`).
- `wb offers guidelines` prints a private per-installation file: the
  guidelines are confidential and don't belong in this repository.
- `wb milestones` is the only command talking to GitHub (through `gh`).

## Domain rules

- `docs/metrics.md` documents every report and key figure. Update it in the
  same commit as the computation, remove fixed "Known inconsistencies".
- Offered amounts and hours only count for open projects; for closed ones
  invoiced amounts and logged hours are ground truth.
- Profitability rather underestimates: when in doubt count hours and leave
  out money. The overall rate counts all budgeted hours, the accepted rate
  only those of accepted offers (offered or logged, whichever is higher);
  hours on unbudgeted services (optional, declined) are added on top.
- Squeeze splits gross margin between people by `HOURS_FOR_INVOICING`
  weighted with the service's rate (`BASE_HOURLY_RATE` for rates of 0).
  Keep figures per person low-key in texts: they're volatile and need
  interpretation. Company-wide totals are fine.
- Third party costs are deducted once: the larger of invoiced and logged
  (`third_party_costs()`), since logged costs can't be linked to fixed
  amount invoices. Offered gross margin: the larger of offered and logged.
- Projected invoices are gross margin without third party costs; not on
  closed projects nor on or before the freeze date. Invoicing uses up the
  oldest projections first; overdue ones stay in their month.
- Cash data API: `accepted_offers_not_invoiced.total_excl_tax` is revenue,
  `not_in_planned_invoicing_excl_tax` gross margin; never subtract one from
  the other. Project-based figures leave out internal projects.
- Value and invoice logged work with `HOURS_FOR_INVOICING`
  (`workbench/logbook/models.py`); everything about time (utilization,
  planning, budgets in hours) uses `hours`.
- Services invoices: services default to the offer if something has been
  offered (not declined), otherwise to the logbook; invoicing the offer
  links the entries logged so far, later entries are the surplus. Services
  of sent or accepted offers only allow changing the external reference;
  invoiced services (`Service.objects.invoiced()`) aren't deleted or moved
  to another project and keep effort type and rate.
- Known gap, left alone on purpose: services can be created on closed
  projects, and logging stays possible for 14 days after closing. Don't
  "fix" it without asking.
- Planning ignores `Service.is_optional` (planned work has
  `is_provisional`). Closed projects get no new planned work; closing
  projects and declining offers deletes planned work after the current week
  (`delete_after_this_week()`), past work stays.
- The planning import prompt goes to external LLMs: people by short name
  only, absences without reason (`plannable_users()`).
- Descriptions of sickness absences may be health data: only the absent
  person and `PERSONNEL_ADMINISTRATION` see them (`details_visible_to()`,
  `description_for()`, `public_text()` for planning and mails;
  `Absence.__str__` has neither reason nor description). Paid leave needs a
  confirmation by `PERSONNEL_ADMINISTRATION`.
- Contacts: groups with `applies_to_organizations` belong to the
  organization, use `Person.all_groups()` / `Person.objects.in_group()`
  instead of `person.groups`. Unused contacts are archived after five years
  (`archive_unused_contacts()`; `_recent()` lists what counts as use, a test
  lists all relations). Merge duplicates (`workbench/contacts/merge.py`)
  instead of deleting: projects, deals and invoices `SET_NULL` their
  contact. Central email addresses and phone numbers of organizations
  aren't copied to their people. Group titles are unique (case-insensitive).
- Offers are only linked to open deals and only while not closed; closing a
  deal settles its offers. The deal owner always contributes
  (`DealForm.clean()`).
- Offer headings share the positions of the services (`Offer.items()`,
  `save_positions()`; `reorder_services()` keeps headings in place).
- Audit log (`LoggedAction`, a database trigger) is keyed by column name:
  renaming a column loses its history unless the migration updates the
  keys. Data migrations of audited tables can't alter the table in the same
  transaction, put schema changes into a separate migration. New audited
  tables need an entry in `prune_audit()` and possibly `HISTORY`
  (`workbench/tools/history.py`).
- Creating notes sends no mail; owners get a daily digest
  (`send_notes_digest()`).

# Deployments

Each installation's deployed commit is the branch `origin/latest/<installation>`
(e.g. `latest/workbench-fhag`). Run `git fetch` and compare them with `main`
to see what is live where, e.g. `git rev-list --count
origin/latest/workbench-fhag..origin/main` for the commits not deployed yet.

# Committing

- Commit feature by feature: one self-contained change per commit, not a single
  batch commit at the end of a session.
- No attribution trailers in commit messages (no `Co-Authored-By:`, no
  "Generated with ..." footers).
- Commit messages are written in English.
- Work on `main` directly, no feature branches. Fast-forward instead of
  creating merge commits whenever possible.
