# Spec: Linking logbook entries to fixed amount invoices

## Goal

Make the logbook and the invoices of a project agree on what has been paid
for, also when invoicing fixed amounts. Today only services invoices can link
logged hours and costs, which leads to third party costs being counted twice
in squeeze (see `specs/squeeze-gross-margin.md`, problem 1) and to work which
could be invoiced twice.

## 1. Today

Logged hours and costs are linked to the invoice which paid for them through
`invoice_service` (a FK to `invoices.Service`), and archived (`archived_at`)
at the same time. Archived entries can't be changed or deleted anymore and
aren't offered again when creating the next invoice from the logbook. The
links are visible on the logbook entry and in the invoice's XLSX export, but
not on the PDF.

Only *services* invoices have services, so only they can link entries:

- From the logbook: the not yet archived entries of the selected project
  services are linked.
- From the offer: the entries existing at that moment are linked. Entries
  logged later stay unlinked (project A's translations).

*Fixed amount* invoices on projects have no services, so nothing can be linked
to them. Besides the double counting in squeeze this has a second effect: the
hours and costs paid for by a fixed amount invoice stay unarchived and are
offered again when the next invoice is created from the logbook. That's why
`Project.create_invoice_warnings()` warns about mixing fixed amount and
services invoices on one project ("Take care to not send invoices for the
same services twice!"). With linked entries this warning could go.

## 2. Link entries to an existing invoice

A "link logbook entries" action on project invoices (fixed amount and
services), allowed in every status including frozen, because it doesn't change
anything the customer sees:

- Select project services; their unarchived logged hours and costs (up to an
  optional cutoff date, as when creating an invoice) get linked and archived.
- The entries are linked to the invoice's service for that project service.
  If there is none, one is created (see 3. for fixed amount invoices). On
  services invoices which aren't in preparation anymore, only project
  services which already have a line can be selected: a new line would change
  the invoice.
- Nothing is recomputed. Services created from the offer keep the offered
  hours and costs, linking only records where the work was paid. Third party
  costs stay as they are and can be corrected separately (see the squeeze spec, 2b).
- The reverse ("unlink") is only allowed as long as the invoice is in
  preparation, as with deleting invoices today.

For a project like project A in `specs/squeeze-gross-margin.md`: link the media budget costs to the three fixed
amount invoices and the translations to the services invoice; afterwards no
unlinked costs are left and squeeze doesn't need the `max()` heuristic for this
project. The heuristic stays for older data and for projects where nobody
links.

## 3. Fixed amount invoices on projects with services

With services on fixed amount invoices, *fixed amount* and *services* differ
only in two places:

| | Services | Fixed amount |
|---|---|---|
| Subtotal | sum of the services | entered |
| PDF | one line per service | no service lines, only the total |
| Third party costs | sum of the services | entered (default: sum of the services) |

So *fixed amount* on a project becomes a way of presenting the invoice rather
than a different kind of invoice. Creating one works like creating a services
invoice: select project services (from the offer or the logbook), entries get
linked; then the subtotal is entered (prefilled with the sum of the selected
services) instead of computed.

The total can be computed in the frontend while selecting services: the
amounts are already in the choice labels, so a few lines of JavaScript can sum
the checked ones and show the total (and the third party costs) next to the
form. Choosing "fixed amount" then mostly means "I want to adjust that total
and show only one line", and could even become a checkbox ("show as fixed
amount") on services invoices instead of a separate type.

Implementation notes:

- `Invoice._calculate_total()` only computes the subtotal from services for
  `SERVICES`; that stays. For `FIXED` the services are informational.
- `PDFDocument.process_invoice()` skips `table_services()` for `FIXED`.
- The invoice detail page lists the services of fixed amount invoices below
  the total, marked as "not shown on the invoice".
- Fixed amount invoices without a project (person invoices) and recurring
  invoices don't change.
- *Down payment* invoices stay as they are. They are applied to a later
  invoice, which is the one the work should be linked to.

## 4. Implementation order

1. Link logbook entries to existing invoices (2.).
2. Fixed amount invoices on projects with services (3.), including the total
   shown immediately while selecting services.

## 5. Open questions

- Should the services selection for fixed amount invoices be optional (as
  today, just enter an amount) or required on projects? Optional is easier to
  introduce; required would make the double invoicing risk from 1. go away for good.
- Merge *fixed amount* into *services* with a "show as fixed amount" flag, or
  keep the type and make them work alike? The flag is cleaner, but existing
  fixed amount invoices (and those created by recurring invoices) need a data
  migration, and project invoices without services stay a special case
  anyway.
