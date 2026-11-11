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
  `user_auth()` in `workbench/accounts/api_auth.py`). Tokens expire
  `API_TOKEN_LIFETIME` after their last use (each use extends them; the fairy
  tasks delete them after another `API_TOKEN_LIFETIME`); `wb login` gets a new one through `/cli-login/` in the
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
  `show` (and `pdf`) take the ID or the code of projects, offers, invoices
  and deals (`by_id_or_code()` in `workbench/api_codes.py`, detail endpoints
  take both).
  Verbs: `search` (optional terms plus filters like `--project`, `--customer`,
  `--owned-by`; the API supports the same filters; what's left out by default
  is included with `--include-closed`, `--include-archived` or
  `--include-inactive`, `include_*` in the API), `show ID`, `create`.
  Nouns without a verb show the most common list (`invoke_without_command`):
  `wb projects` your open projects, `wb hours` your hours of this week, `wb
  offers`/`invoices`/`deals` yours which may need action (like `wb me`), `wb
  users`, `wb teams`, `wb campaigns`, `wb auth` the installations; nouns which need a search
  term show the help. `wb search` searches everything like the search field
  of the web interface (`/api/search/`, sources shared with the web view in
  `workbench/search.py`).
  The package `cli/wb/` has one module per noun (`wb/offers.py`); `wb/core.py`
  has the configuration, requests, output helpers and options they share.
  `wb contacts search` finds both organizations and people, `wb organizations
  show` and `wb people show` show them. `wb organizations search` filters
  organizations (`--without-active-people`, `--primary-contact`), `wb
  organizations update` changes their primary contact and archives them,
  `wb organizations merge ID --into ID` merges duplicates
  (`OrganizationMergeForm`, `merge_organizations()`). `wb people search` filters people like
  the people list of the web interface (`--group`, also through the
  organization, `--without-groups`, `--missing-postal-address` like the
  defined search, `Person.objects.without_complete_postal_address()`,
  `--primary-contact`,
  `--projects-or-deals-since` like the defined search of the last five
  years, `recent_projects_or_deals()`) and has the postal address the XLSX
  export of the people list uses (highest weight), so scripts can build
  mailing lists without fetching every person. `wb
  people update` changes the primary contact, adds and removes groups and
  archives people (`PATCH /api/contacts/people/<id>/`); groups which apply
  to organizations go to the organization like in the person form
  (`Person.add_to_group()`, `remove_from_group()`). `wb people
  reassign-suggestions` and `wb people reassign` move the people of users who
  left (`/api/contacts/people/reassign/`): suggestions are the lead of the
  latest project or the owner of the latest deal (whichever is newer), the person's own before
  their organization's, only active users (`primary_contact_suggestions()` in
  `workbench/contacts/reassign.py`); people without a suggestion stay. `wb people merge ID --into ID`
  merges duplicates (`POST /api/contacts/people/<id>/merge/`, also in the
  web interface, `PersonMergeForm`; organizations are merged in the web
  interface only, `merge_organizations()`; possible duplicates (the same name, or the same email address and a
  common given or family name) are listed on the person, globally and by
  `wb people duplicates`, `possible_duplicates()`; organizations with the
  same name (case and whitespace ignored) or central email address are
  listed globally, archived ones included,
  `possible_organization_duplicates()`; `merge_people()` in
  `workbench/contacts/merge.py`): reverse relations move with
  `substitute_with()`, groups are added with `add_to_group()`, details the
  person kept has already are dropped, notes are appended, the person kept
  is archived only if both were, an inactive primary contact is replaced
  by the duplicate's active one (organizations too); people who are
  both linked to a user can't be merged. Merging into someone of another
  organization is a warning (`other-organization`) if the duplicate is the
  contact of projects, deals, invoices or recurring invoices: forms only check that the contact
  belongs to the customer when one of them changes, so those stay editable. Projects, deals and invoices
  `SET_NULL` their contact, so deleting a person without merging loses
  those links. `wb groups` lists, creates
  and archives groups (`/api/contacts/groups/`, with `GroupSearchForm` and
  `GroupForm` of the web interface); titles of groups are unique
  (case-insensitive, `GroupForm` and a constraint) because the other
  endpoints find groups by their title. `wb people create` is mostly fed by
  LLMs, so the API rejects duplicate names and email addresses (the web
  interface doesn't), and archived people with the same name and
  organization (or both without), who should rather be unarchived. Its `primary_contact` defaults to the current user and
  may be an inactive user (e.g. who used to know the person), so that imported
  contacts can be found and reassigned with the primary contact filter.
  Warnings of the web forms are errors in the API which carry their code;
  like in the web interface, only the warnings whose codes are given in
  `ignore_warnings` are ignored (a query parameter like `dry_run`,
  `--ignore-warning CODE` in `wb`; `validate_form()` in
  `workbench/tools/api.py`), so ignoring one never ignores a new one. Request
  bodies (also nested objects) derive from `InputSchema` in
  `workbench/tools/api.py` and reject unknown fields: data an LLM puts under
  a wrong key would otherwise be lost silently (a test checks the OpenAPI
  document). Shared validation helpers for the APIs are in
  `workbench/tools/api.py`, also `DateRangeFilter` (`period` like `2026-Q3` or
  `last-month`, `since`, `until`) with `date_range()` and `filter_date_range()`
  for reports and searches, and `UsersFilter` with `filter_users()` for
  reports. Cutoff dates are called `date`. Reports live at
  `/api/reports/<name>/` with the names of `wb reports`; key data and cash
  data are also served at their old URLs (`/api/key-data/`, `/api/cash-data/`,
  hidden from the schema) for integrations. Responses have schemas and decimals are
  strings everywhere (`Amount`, `Hours`, `Days` and `Percentage` in
  `workbench/tools/api.py` round computed values), except key data and cash
  data which use `jsonable()` for the integrations. Statuses and
  probabilities are stored as numbers for their natural ordering; the APIs
  output and accept stable keys instead (`KEYS` in `workbench/api_keys.py`,
  a test checks that they are a bijection with the model's choices). Choices
  stored as strings (invoice types, absence reasons, …) are their own keys.
  Outputs never use display strings for choices: main objects have the key
  and a localized `*_label`, and `/api/choices/` lists all of them.
  All errors are `{"detail": [{"loc": [...], "msg": ..., "code": ...}]}` like
  validation errors (`HttpError` and 404 too, `WorkbenchAPI` in
  `workbench/api.py` documents them as `4XX`); only the upgrade notice for
  outdated CLIs stays a plain message, which old versions can show.
  Schema classes have unique names across all routers (ninja names the
  OpenAPI components by class, duplicates overwrite each other; a test in
  `workbench/test_api_schema.py` checks it), and query parameters have
  descriptions (`SearchQuery`, `ShortName`, … in `workbench/tools/api.py`).
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
  reads it and tells users of older versions to upgrade; the CLI warns when
  the server's version is older than its own (not deployed yet). Raise
  `MINIMUM` in `workbench/cli_version.py` when older versions don't work
  anymore.
  The CLI requires the same Python as the server (ruff's target version
  applies to it too); `uv tool install` fetches it, but `uv tool upgrade`
  keeps the old Python, so the server tells the CLI the upgrade command with
  `--python` (`UPGRADE` in `workbench/cli_version.py`).
  `workbench/test_cli.py` runs the real CLI commands against the API (requests
  go through Django's test client); add a test there for new commands. The CLI
  is installed with the project's dev dependencies, not in the container.
  `wb invoices send-reminder CONTACT --to EMAIL` sends dunning letters like
  the web interface (`SendReminderForm`, bookkeeping feature); without
  `--to` it only shows the addresses and invoices.
  `wb invoices create` (`POST /api/invoices/`) only creates invoices in
  preparation, validated with the web interface's creation forms
  (`CreateProjectInvoiceForm`, `CreatePersonInvoiceForm`, built with the
  query parameters of the web views) and their defaults; sending them stays
  in the web interface. Paid and cancelled invoices require a payment notice;
  assigning a credit entry writes its date, ledger, amount, payment notice
  and notes into it (`CreditEntry.mark_invoice_as_paid()`).
  Values given by name have a listing which shows them with their ID
  (`wb projects internal-types`, `wb deals value-types`, `wb deals
  attributes`); internal types are taken by name or ID.
  `wb invoices pdf` and `wb offers pdf` save the PDFs of the web interface
  (`/api/invoices/<id>/pdf/`, `/api/offers/<id>/pdf/`; `download()` in
  `wb/core.py` keeps the file name of the response).
  Hours are not logged through the CLI on purpose: the warnings of the web
  interface's logbook forms are useful. The offers API (`workbench/offers/api.py`) only changes offers
  in preparation: create, replace and update, with the rules of
  `_apply_service()` for their services (single services through
  `/api/services/`). Creating
  also allows service groups (`status: service_group`, which may have no
  services yet) and external references. Only the
  external references (URLs, one per line) can be changed for offers in any
  state, the external reference of services too (`PATCH /api/services/<id>/`,
  `wb services update`, also in the web form); Workbench stores them but
  doesn't talk to GitHub. `wb milestones` (the only command which talks to
  GitHub, through `gh`) links GitHub milestones with offers through these
  references and creates milestones and service groups for each other. Single services are created, changed, moved between offers, deleted and
  reordered through `/api/services/` (`wb services create/update/delete/reorder`),
  validated with the web interface's `ServiceForm` (which also restricts the
  offer queryset, not only the choices; it warns only about the changed
  title and description, the API treats those warnings like elsewhere) and
  its rules: services of offers which
  have been sent or accepted only allow changing the external reference,
  deleting is only possible in offers in preparation, service groups or without offer and
  without logged hours or costs, invoiced services (`Service.is_invoiced`,
  also from the offer; cancelled invoices don't count, `Service.objects.invoiced()`) are neither deleted nor moved to another
  project and keep their effort type and rate (also when the project gets a
  flat rate); they may move to another offer of their project (the invoice
  lines still point to them, archived logbook entries prevent invoicing
  them twice), reordering takes all services of one offer
  (or the services without offer of one project). `POST
  /api/services/<id>/reassign-logbook/` (`wb services reassign-logbook`)
  reassigns logged hours and costs with `ReassignLogbookForm`; invoiced
  entries only with `include_invoiced`. Messages added during API requests
  are dropped (`api_messages_middleware` in `workbench/middleware.py`), they
  would show up later in the web interface. `POST
  /api/services/<id>/merge/` (`wb services merge ID --into ID`, also in the
  web interface; `ServiceMergeForm`, `merge_services()` in
  `workbench/projects/merge.py`) merges a service into another one of the
  same project: the logbook (invoiced entries too), invoice lines,
  timestamps and pins move with `substitute_with()`, the service is
  deleted. Not for services of offers which have been sent
  (`Offer.services_changeable`, service groups can); different effort types or rates are a warning
  (`different-rate`). `wb offers
  guidelines` prints a private file configured per installation in the wb
  configuration (`offer_guidelines`), which the `workbench-offer` skill
  follows; the guidelines contain confidential figures, so they don't live in
  this public repository. Service types only suggest the effort type
  and the hourly rate, both can be set freely.
- Timestamps may have a project and a service which pre-fill the logbook form
  of their slice (`wb ts start -p profond`). The API accepts a project ID or a
  full text search of open projects (`-p "profond kennzahlen"`, the existing
  index which also covers descriptions); a unique match among the user's
  pinned projects wins, otherwise the match among all open projects has to
  be unique (`timestamp_project()` in `workbench/timer/models.py`).
- Short names (`User._short_name`) are unique when case folding, unless blank.
  APIs identify people by their short name and match it case-insensitively;
  filters reject unknown ones (`user_by_short_name()` in
  `workbench/tools/api.py`) instead of finding nothing.
- The planning import (`wb planning import`) adds entries without an `id`,
  updates those with one (only the given fields) and deletes the IDs listed
  in `delete_milestones` and `delete_planned_work`; the context has the IDs.
  Single planned work is added, changed and deleted with `wb planning work
  add/update/delete` (`/api/projects/<id>/planning/work/`,
  `/api/planning/work/<id>/`). All of them validate with
  `_apply_planned_work()` in `workbench/planning/api.py`.
- The planning import prompt is pasted into external LLMs. Keep personal data
  out of it: people are identified by their short name only (no email
  addresses or full names, see `plannable_users()` in
  `workbench/planning/api.py`), and absences have no reason.
- Offered amounts and offered hours only count for open projects; for closed
  projects the invoiced amount and the logged hours are ground truth.
- Known gap, left alone on purpose: services can still be created on closed
  projects (web and API; offers can't), although closed projects don't
  offer their services and logbook prominently. Logging stays possible for
  14 days after closing (`Project.is_logbook_locked`). Not a problem in
  practice, so don't "fix" it without asking.
- `docs/metrics.md` documents how every report and key figure is computed.
  Update it in the same commit when you change a computation, and remove
  entries from its "Known inconsistencies" when you fix them.
- `project_gross_margin(project)` in `workbench/reporting/squeeze.py` computes single-project profitability (gross margin, rate, offered/projected/invoiced breakdown). Use this instead of duplicating squeeze logic.
- Profitability estimates (rates, gross margins) should rather underestimate
  than overestimate. When in doubt, count hours and leave out money.
  The overall rate counts all budgeted hours (also from offers not accepted
  yet); the rate based on accepted offers only their hours (offered or
  logged, whichever is higher). Hours logged on
  services which aren't budgeted (optional, declined) are added on top.
- Squeeze splits a project's gross margin between people by the value of
  their work: hours for invoicing (`HOURS_FOR_INVOICING`) weighted with the service's
  hourly rate. The project's share of the period and all rates use `hours`.
  Services without a rate or with a rate of
  0.00 (work paid elsewhere, e.g. by a package price) are weighted with
  `BASE_HOURLY_RATE`. Describe it briefly in help texts and docs, without
  emphasizing the figures per person: they are volatile and need a lot of
  interpretation and care, also because of different employment profiles.
  Company-wide totals are fine.
- Third party costs are deducted once: the larger of those on invoices and
  the logged ones (`third_party_costs()` in `workbench/reporting/squeeze.py`).
  Logged costs can't be linked to fixed amount invoices, so adding up both
  would count them twice. This applies to squeeze and to the invoiced gross
  margin which uses up projected invoices alike. The offered gross margin
  deducts the larger of the offers' third party costs and the logged ones.
- Projected invoices (`ProjectedInvoice.gross_margin`) are gross margin, third
  party costs are not included. They aren't added to closed projects nor
  dated on or before the freeze date (`ProjectedInvoiceForm`). Invoiced gross margin uses up a project's
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
- `LoggedHours.hours_for_invoicing` (optional) is what the work is worth if that
  is more than the time spent (the form warns about lower values and much
  higher ones, see `hours_for_invoicing_much_higher()`; it can be changed
  late, until the entry is archived). Value and
  invoice logged work with `HOURS_FOR_INVOICING`
  (`Coalesce("hours_for_invoicing", "hours")` in `workbench/logbook/models.py`,
  annotate querysets with it); everything about
  time (utilization, productivity, planning, squeeze's hours, budgets in hours)
  uses `hours`.
- Everyone may know that someone is sick (the team talks about it anyway),
  but the descriptions of sickness absences may be health data ("besonders
  schützenswerte Personendaten"): only the absent person and users with
  `PERSONNEL_ADMINISTRATION` see them and may edit those absences
  (`Absence.details_visible_to()`, `description_for()`, the `absences`
  template filters; absences can't be searched, the reason filter finds
  them). Changing the reason away from sickness while keeping the
  description is an error (the description would become public) with a
  link to a new absence with the new reason and without the description,
  which replaces the old one when saved (`replaces`, only for those who may
  delete it). `Absence.__str__` contains neither reason nor
  description. Planning and its mails use `public_text()`. The annual
  working time summary (balance, vacation, planned absences) is for
  everyone because it helps planning; the details of others (also
  sickness days) require the feature; the history shows
  descriptions only with it, and `clear_sickness_descriptions()` (fairy
  tasks) clears descriptions and history after three years, like the audit
  log pruning of absences.
  Descriptions of absences are optional. Paid leave counts right away but
  needs a confirmation by someone with `PERSONNEL_ADMINISTRATION`
  (`Absence.needs_confirmation`, `update_confirmation()` in the form,
  `Absence.objects.unconfirmed()`, listed under "needs action"); paid
  leave they enter is confirmed, editing someone's isn't a confirmation.
  Anyone may enter absences for others, but only the person and people with
  `PERSONNEL_ADMINISTRATION` change and delete them (`Absence.allow_update`);
  whoever entered them may still undo mistakes on the same day, as long as
  nobody else changed them (`only_changed_today_by()`, from the audit log).
- Contacts unused for five years are archived (`archive_unused_contacts()` in
  `workbench/contacts/tasks.py`, fairy tasks). Reverse relations are
  discovered with `_meta.get_fields()`; `_recent()` says which related
  objects count as recent use, contacts referenced by models missing there
  are always kept (a test lists all relations). Membership in groups which
  aren't archived keeps people (not organizations: those without active
  people are useless for mailings), so do edits in the audit log.
  Archiving the last active person of an organization (person form and
  API) archives it too, unless it has open projects or deals; unarchiving
  a person unarchives their organization (`update_organization_archival()`),
  so do creating, moving and merging active people into an archived one
  (`unarchive_organization()`).
  People who left move to their new organization or to none (person form,
  `wb people update --organization`); moving the contact of projects, deals
  or invoices warns (`organization-update`, `organization_update_warning()`),
  they keep their customer and contact; `--remove-postal-address ID`
  removes the old organization's addresses, `--postal-address-type ID TYPE`
  fixes the type, e.g. of private addresses saved as work addresses.
  The types of email addresses, phone numbers and postal addresses are free
  text; the forms suggest `PersonDetail.TYPES` (Work, Mobile, Home, Fax,
  `SuggestionsInput`, `initSuggestions` in `main.js`), which keep their
  spelling when saved. Details copied from the organization by an old import
  start with `organization` and come last (`PersonDetail.WEIGHTS`). Former employees stay in an
  active group (e.g. the team's) so they aren't archived.
  Archiving an organization warns about its active people
  (`archive-people`, form and API) and archives them when confirmed
  (`Organization.archive_warning()`, `archive_people()`).
  Postal addresses belong to people; the person form copies those of
  colleagues and the organization changes one address of several people
  at once (`organization_postal_addresses()`, `OrganizationPostalAddressForm`;
  `wb organizations show` lists them, `wb organizations change-address`,
  `wb organizations search --several-postal-addresses` finds outdated ones,
  private addresses (`HOME_TYPE`) don't count).
  Organizations have a central email address (e.g. info@, shown on their
  people, so it doesn't belong on them) and an optional accounts payable
  address; payment reminders suggest the accounts payable address, the
  contact's addresses and the central address, in this order. `wb people
  shared-emails` lists addresses of several active people of the same
  organization (usually generic ones) and central addresses still on
  people; `wb people update --remove-email` removes them. The API doesn't
  add central addresses to people. Organizations also have a central phone
  number (normalized like those of people, `normalize_phone_number()`),
  shown on their people; the API doesn't add it to their people. `wb people
  shared-phones` and `--remove-phone` work like their email counterparts
  (`_shared_details()`).
- Groups with `applies_to_organizations` (e.g. industries) belong to
  organizations: people are in them through their organization
  (`Person.all_groups()`, `Person.objects.in_group()`, `without_groups()`;
  use these instead of `person.groups`). The person form still offers them
  but saves them on the organization; only people without an organization
  are members themselves. Turning the flag on moves existing memberships to
  the organizations (`Group.move_people_to_organizations()`), turning it off
  makes their people members (`move_organizations_to_people()`).
  Pinned groups (`is_pinned`, e.g. the company's own) come first wherever
  groups are listed (`Group._meta.ordering`, `Person.all_groups()`); `wb
  groups update --pin`.
- Offers are only linked to and unlinked from open deals, and only offers
  which aren't closed yet (in preparation, service group, offered): closing a
  deal settles its offers (those in preparation, which customers may have
  received as drafts, and offered ones are preselected; settled offers,
  also those of a reopened deal, only when selected; missing offer and
  validity dates become the deal's closing date; declining service groups
  discards them). Offers of other customers' projects are a warning
  (agencies and their clients, departments of a city), `other-customer` in
  `ignore_warnings` in the API.
  Web views and API share `RelatedOfferForm` in `workbench/deals/forms.py`.
- The owner of a deal always contributes to it (`DealForm.clean()`); the
  accepted deals report splits a deal's value between the contributors by
  weight. The API adds the owner with weight 100 when creating deals;
  changing the owner moves the old owner's contribution to the new one
  (`DealForm.clean()`, web and API) unless the contributions of either are
  changed too (`contributions` by short name, `wb deals update
  --contribution ab=0`).
- The audit log (`LoggedAction`, filled by a database trigger) stores
  `row_data` and `changed_fields` as hstore keyed by column name. Renaming a
  field or column loses its history: old entries keep the old key. Only
  rename on purpose, and update the keys in the migration if the history
  matters. The history (`HISTORY` in `workbench/tools/history.py`) lists
  related objects by a foreign key, or through generic relations
  (`generic_related()`, e.g. the notes of an object, with `content_type_id`
  as an additional filter); a config may restrict the actions and the
  instances a user sees (`actions`, `allow`; notes need the feature of
  their object). `prune_audit()` (fairy tasks) deletes the history of data after
  two, three or five years (size and data protection); users, employments
  and the configuration stay. New audited tables need an entry there.
- Creating notes sends no mail. The fairy tasks send owners one daily digest
  with titles, truncated descriptions and links of the notes others added or
  edited on their deals, invoices and projects the day before, found in the
  audit log (`send_notes_digest()` in `workbench/notes/tasks.py`), only of
  objects their features let them see (`visible_content_types()`).
- Planning does not care about `Service.is_optional`; planned work has its own
  `is_provisional` flag for definitive vs. provisional work. Closed projects
  get no new planned work, external work or milestones (web and API), and
  their planned and external work doesn't get weeks after the current one
  (`future_weeks_on_closed_project()`); closing a project (also its external
  work),
  declining or discarding an offer and declining a deal offer to delete the
  planned work after the current week (entries spanning it are shortened,
  their hours reduced accordingly; `PlannedWorkQuerySet.delete_after_this_week()`).
  Past work stays for the comparison with the logbook.
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
  Collapsed content uses `hidden="until-found"` (not Bootstrap's
  `.collapse` or CSS line clamps) so that the browser's search finds and
  reveals it; long descriptions use `{% clamped %}`.
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
