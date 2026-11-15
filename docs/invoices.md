# Invoices

| Type | |
| --- | --- |
| Fixed amount | An amount, with a title and a description. The simplest type when the invoice doesn't have to list the services. |
| Down payment | An amount on a project, deducted from later invoices. |
| Services | Services of the project, as offered or as logged. |
| Credit | An amount credited to the customer, entered as a positive number. |

## Creating an invoice

On the project, "New" lists the types under "Invoice"; "Create invoice"
in an offer's menu creates a services invoice for that offer. For a fixed
amount and a down payment, the amount's help offers percentages of the
accepted offers. Workbench warns when the project already has an invoice
in preparation and when mixing fixed amount and services invoices, which
risks invoicing the same work twice.

"This is the final invoice, close the project" closes the project when
saving.

Customers are always organizations. For a private person, create an
organization and tick "is private person": its name is then left out of
addresses. Invoices without a project (e.g. selling old equipment) are
created from a person or an organization with "New" → "Invoice"; they
can only be fixed amounts.

## Services invoices

At the top, choose the offer to invoice or "No offer, select services
yourself". Choosing an offer takes its title, description, services and
discount. Per service, **invoicing** chooses the source:

- **as offered**: the offered hours and costs. The default when something
  has been offered, the offer hasn't been declined and the service hasn't
  been invoiced yet. It also links the entries logged so far.
- **as logged**: the hours and costs logged and not invoiced yet. After
  the offer has been invoiced, that's the **surplus**: work logged
  afterwards.

The lines can be adjusted (hours, rate, costs, title, description).
Hints show logged hours and costs which aren't invoiced as offered. The
**logbook cutoff date** leaves later entries for the next invoice, and
"disable logging" closes a service for logging. Only services with
something to invoice are listed, "List all services of the project"
shows the rest. A service invoiced with 0 still links its open entries,
which writes them off.

## Down payments

Fixed amount and services invoices on a project with down payments
offer "Apply down payment invoices": the down payments sent or paid and
not applied yet are deducted. A down payment applied to a sent invoice
can't be changed anymore; cancel that invoice first.

## Sending, payments and cancelling

| Status | |
| --- | --- |
| In preparation | Being written, can be deleted. |
| Sent | Needs the invoice date and the due date. |
| Paid | Needs a payment notice. |
| Canceled | Needs a payment notice saying why. |

- **Release and send** mails the PDF to the recipient, marks the invoice
  as sent and sends its owner a copy.
- **Mark as paid** in the invoice's menu, or by assigning a payment (see
  below).
- Invoices **in preparation** are deleted, sent ones are **cancelled**
  ("Cancel invoice"). Both release the logged entries and down payments
  for another invoice. A cancelled services invoice or one with down
  payments can't be reopened: create a new invoice instead.

Workbench lets you change sent invoices, but warns. The warnings are
meant as help: if the changed invoice is what it should have been from
the beginning, choose "Ignore warnings". Be careful when the invoice has
been paid already or has reached the bookkeeping. Invoices on or before
the freeze date are frozen: only their status and a few fields can be
changed.

## Recurring invoices

"Payments" → "Recurring invoices" creates fixed amount invoices
periodically (yearly, quarterly, monthly or weekly), a number of days
before each period begins. New invoices are created in preparation,
marked as sent, or mailed automatically; the owner gets a mail.

## Payments and reminders

With access to bookkeeping:

- **Credit entries**: "Upload account statement" imports the bank's
  statement, "Assign credit entries" assigns each payment to the sent
  invoice with the same total, which marks it as paid.
- **Reminders** lists invoices overdue by 15 days or more, by customer,
  and creates or mails the reminder. "Postpone reminders" on an invoice
  holds them off for up to 60 days.

How invoices start: see [Offers](offers.md).
