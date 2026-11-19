# Invoices

| Type | |
| --- | --- |
| Fixed amount | An amount, with a title and a description. The simplest type when the invoice doesn't have to list the services. |
| Down payment | An amount on a project, deducted from later invoices. |
| Services | Services of the project, as offered or as logged. |
| Credit | An amount credited to the customer, entered as a positive number. |

## Creating an invoice

On the project, "New" lists the types under "Invoice"; "Create invoice"
in an offer's menu creates a services invoice for that offer. Workbench warns when the project already has an invoice
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
discount. The whole discount, until an invoice of the offer's services
(not cancelled) carries a discount: a first partial invoice without
discount doesn't use it up, invoicing the surplus doesn't get it again.
Invoices without offer start without discount. Per service,
**invoicing** chooses the source:

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

Lines show their third party costs, the totals the services excl. third
party costs. If offers of the project have a discount, the discount's
help lists them (with their percentage of the services excl. third party
costs), compares what the accepted offers granted with the discounts of
the invoices so far and fills in the remaining discount, the offers'
percentages of this invoice's services excl. third party costs, or any
other percentage. What matters is that the customer gets the discounts
once in total, not which invoice carries them; if less was delivered
than offered, a smaller discount may be right.

## Fixed amounts and down payments

The amount's help shows the total excl. tax of the accepted offers
(after their discounts) and what has been invoiced so far. "Invoiced so
far" is the work invoiced (subtotal minus discount of the fixed amount
and services invoices), down payments are listed separately with the
part which hasn't been applied yet. A fixed amount invoice can fill in
the rest: the down payments it applies are deducted from it, not counted
twice.

A percentage fills in that share of the accepted offers or, if their
services have third party costs, of the accepted offers without third
party costs, rounded to 5 cents. Down payments and fixed amount invoices
show no discount: their base is after the offers' discounts already.

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
marked as sent, or mailed automatically (the list filters by it); the
owner gets a mail. With
"Create project?" each invoice gets its own maintenance project and is a
down payment on it, deducted when the work logged there is invoiced.
The invoices link to their recurring invoice, which lists them.

## Payments and reminders

With access to bookkeeping:

- **Credit entries**: "Upload account statement" imports the bank's
  statement, "Assign credit entries" assigns each payment to the sent
  invoice with the same total, which marks it as paid.
- **Reminders** lists invoices overdue by 15 days or more, by customer,
  and creates or mails the reminder. "Postpone reminders" on an invoice
  holds them off for up to 60 days.

How invoices start: see [Offers](offers.md).
