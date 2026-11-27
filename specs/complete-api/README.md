# Spec: A complete API and `wb`

## Goal

Handing over the open work of someone who left (November 2026) showed
gaps: `wb` changed projects and deals, but offers and invoices had to be
reassigned in the browser. The gaps send agents back to automating the
browser, which is worse than the API in every respect: the browser can
click "ignore warnings" for all of them at once, while the API makes the
caller name each warning it ignores (`ignore_warnings`, codes from
`validate_form()`). That reasoning already opened logging hours and costs
to the API; this spec applies it everywhere.

Wanted: everything a user can change in the web interface can be changed
through the API and `wb`, with the same rules, the same permissions and
the same warnings. No restrictions that exist only in the API.

## Decisions (apply to every package)

- **The web form is the rule.** Writes go through the form the web
  interface uses (`form_data()` with the instance's current values, the
  patched fields on top, `validate_form()`), like
  `PATCH /api/projects/{id}/` already does. Whatever the form allows, the
  API allows; whatever the form refuses or disables, the API refuses with
  the form's error. No second set of rules in the API.
  - Example: the invoice form lets sent invoices change their owner, title,
    description, status (to paid or cancelled), closed on and payment
    notice. The API gets exactly that.
- **Warnings are errors with a code** unless listed in `ignore_warnings`.
- **Every write takes `dry_run`**: validate, roll back, return what would
  have been saved. Deletions too.
- **Deletions like in the web interface**: they're how mistakes get fixed
  (a wrong offer, an invoice created twice, a misassigned break). They go
  through `check_allow_delete()` and the view's delete form
  (`OfferDeleteForm`, `InvoiceDeleteForm`, ...); the questions those forms
  ask become explicit parameters. What the web interface refuses to delete
  stays refused. **Except contacts**:
  people, organizations and groups are archived or merged, not deleted,
  for now (both are in the API already; a contact created by mistake is
  usually a duplicate to merge).
- **Same permissions and features** as the views (`controlling_only`,
  `deals_only`, `bookkeeping_only`, `hosting_only`,
  `PERSONNEL_ADMINISTRATION`, ...). Read-only tokens never write.
- **The API sends nothing, for now.** Invoices and dunning letters are
  sent from the web interface, recurring invoices by Workbench itself.
  Changing a status (e.g. to sent) never sends anything. Asking for
  overdue invoices (`wb invoices reminders`) is fine; the endpoints which
  sent dunning letters and marked invoices as reminded have been removed.
- **The CLI stays thin**: `wb <noun> update|delete|<verb>`, options named
  like the API fields, `--ignore-warning CODE` (repeatable) and `--dry-run`.
- **Out of scope**: sending mail, bookkeeping (credit entries, bank
  statements, expense reports), personnel administration (confirming paid
  leave), the own user profile, admin-only models, the planning UI's drag
  and drop, reports, file exports beyond the existing PDFs. The coverage
  test of package 00 lists them in `NOT_IN_API` with the reason.

## Working on a package

Each file below is one package, meant to be handed to one agent. The
agent reads `AGENTS.md`, this README and its package file, and:

1. Writes failing tests first: API tests in the app's `test_api.py`, a CLI
   round trip in `workbench/test_cli.py`.
2. Implements the endpoints with the helpers from package 00, mirroring
   the web view named in the package (read the view, its form and its
   template for the confirmations it asks).
3. Updates `cli/README.md`, the skills which benefit (`cli/wb/skills/`),
   the German translations (`conf/locale/de/LC_MESSAGES/django.po`, then
   `fl cm`) and the help pages if they mention the limitation.
4. Runs `./runtests.sh` for the touched apps plus `workbench.test_cli`,
   `workbench.test_api_schema` and `workbench.test_api_queries`.
5. Commits one endpoint or noun per commit, **without** bumping the CLI
   version: whoever merges the packages bumps `cli/pyproject.toml` and
   `uv.lock` once per batch (they'd conflict otherwise).
6. Ticks its line in the index below and removes answered questions from
   its file.

Agents working in parallel use worktrees. Packages touching the same
`api.py` or CLI module can still run in parallel, but expect small merge
conflicts; the "Touches" column shows them.

## Index

| # | Package | Touches | Depends on | Status |
|---|---|---|---|---|
| 00 | [Groundwork](00-groundwork.md) | `tools/api.py`, forms (warning codes), `test_api_schema.py` | — | done |
| 01 | [Offers: update and status](01-offers-update.md) | `offers/api.py`, `cli/wb/offers.py` | 00 | done |
| 02 | [Offers: copy, delete, renumber](02-offers-copy-delete.md) | `offers/api.py`, `projects/api.py`, `cli/wb/offers.py` | 00 | open |
| 03 | [Invoices: update and delete](03-invoices-update-delete.md) | `invoices/api.py`, `cli/wb/invoices.py` | 00 | open |
| 05 | [Invoices: services](05-invoice-services.md) | `invoices/api.py`, `cli/wb/invoices.py` | 00 | open |
| 06 | [Recurring invoices](06-recurring-invoices.md) | `invoices/api.py` (recurring part), `cli/wb/invoices.py` | 00 | open |
| 07 | [Projects: all fields, delete, projected invoices](07-projects.md) | `projects/api.py`, `cli/wb/projects.py` | 00 | open |
| 08 | [Services: move](08-services-move.md) | `projects/api.py` (services), `cli/wb/services.py` | 00 | open |
| 09 | [Logbook: move entries](09-logbook-move.md) | `logbook/api.py`, `cli/wb/logbook.py` | 00 | open |
| 10 | [Budget transfers](10-budget-transfers.md) | `projects/api.py`, `cli/wb/projects.py` | 00 | open |
| 11 | [Campaigns](11-campaigns.md) | `projects/api.py`, `cli/wb/campaigns.py` | 00 | open |
| 12 | [Breaks](12-breaks.md) | `logbook/api.py`, `cli/wb/logbook.py` | 00 | open |
| 13 | [Planning: milestones and external work](13-planning-milestones.md) | `planning/api.py`, `cli/wb/planning.py` | 00 | open |
| 14 | [Planning: batch update](14-planning-batch.md) | `planning/api.py`, `cli/wb/planning.py` | 00 | done |
| 16 | [Contacts: change and remove details](16-contact-details.md) | `contacts/api.py`, `cli/wb/contacts.py` | 00 | open |
| 17 | [Notes](17-notes.md) | `notes/api.py`, `cli/wb/notes.py` | 00 | open |
| 18 | [Absences](18-absences.md) | `awt/api.py`, `cli/wb/absences.py` | 00 | open |
| 19 | [Teams](19-teams.md) | `accounts/api.py`, `cli/wb/users.py` | 00 | open |
| 22 | [Hosting: delete, contact roles](22-hosting.md) | `hosting/api.py`, `cli/wb/sites.py`, `cli/wb/servers.py` | 00 | open |
| 23 | [Timestamps: split](23-timestamps-split.md) | `timer/views.py` (`split_timestamp`), the timestamps API, `cli/wb/timestamps.py` | 00 | open |

## Decided (2026-11-27)

- Deletions: like in the web interface, except contacts (archive or
  merge); the package for deleting contacts is dropped.
- Sending mail: not through the API; package for sending invoices dropped.
- Bookkeeping, personnel administration and the own profile: not in the
  API; packages for credit entries and expense reports dropped. Teams yes.
- Putting accepted offers back into preparation through the API: yes, it's
  the defined workflow for changing an offer (package 01).
- Dunning letters: the endpoints sending them and marking invoices as
  reminded are removed (wb 0.56.0).
- Order: 00 first, then 03, 01 and 14 in parallel (today's handover gaps,
  three different apps), then the rest in waves of different apps.
