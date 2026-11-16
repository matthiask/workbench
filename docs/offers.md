# Offers

Workbench offers and invoices **services**: work packages such as "Contact
form", priced with hours and an hourly rate and with costs, not bare
hours. An offer belongs to a project and consists of some of its services.
Offers and invoices need access to controlling.

## Creating an offer

On the project, "New" → "Offer" (or "+ Offer" next to "Not offered yet")
opens the offer form. Its title defaults to the project's. Below the
offer's details you add the services:

- **New service** adds an empty row.
- **Existing service** adds one of the project's services which isn't in
  an offer yet.
- **Heading** adds a heading between the services, with a title and a
  description and without amounts.

Drag the rows to sort them. The cross removes a service from the offer,
it goes back to "Not offered yet" and isn't deleted.

Each service has a title, a description, the effort type and the hourly
rate (the service type fills in both), hours, costs and whether it's
optional. Third party costs, "allow logging" and the external reference
are set in the service's own form on the project.

## Prices

- A service costs its hours times its hourly rate plus its costs.
- A service has **one** effort type and hourly rate, which also applies to
  the hours logged on it. Offer work at different rates as separate
  services.
- **Third party costs** are the part of the costs paid to others
  (including tax), not added on top.
- **Optional** services don't count towards the total; the PDF lists
  them with their own total.
- The total is the sum of the services minus the discount, plus VAT,
  rounded to five cents.
- On projects with a flat rate, new services get the flat rate.

## Statuses

| Status | |
| --- | --- |
| In preparation | Being written, the services can be changed. |
| Service group | Never sent: groups services, e.g. for logging and budgets. The services can be changed. |
| Offered | Sent to the customer; needs "offered on" and "valid until". |
| Accepted | The customer agreed. |
| Declined | The customer said no, or a sent offer isn't pursued anymore. |
| Discarded | Never sent and not pursued anymore. |

The services of offered, accepted and declined offers stay as they were
sent. To change them, set the offer back to "In preparation" and save,
then edit the services. Offered and accepted offers can't be deleted.

Declining or discarding an offer asks whether to delete its planned work
after the current week. Closing a project discards its offers in
preparation and declines those sent before.

**Work completed on** ends logging on the offer's services. A **budget
retainer** only retains budget: no hours are logged on its services, the
work is logged on services without offer created later, which free the
retained budget.

## Copies, PDFs and deals

- "Copy" in the offer's menu copies it with its services and headings
  into an open project, in preparation and without dates.
- "PDF" shows the offer, its menu downloads it, also with a signature
  line. Offers which haven't been offered or accepted carry their status
  as a watermark. "Project offers" in the project's menu combines the
  offers of the project, without the declined and discarded ones.
- Offers are linked to deals on the deal ("Link offer"). Closing the deal
  accepts or declines its offers.

How offers become invoices: see [Invoices](invoices.md).
