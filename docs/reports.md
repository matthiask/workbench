# Reports

The "Reports" menu shows the reports you have access to. Most figures
are estimates which rather underestimate: when in doubt, Workbench
counts hours and leaves out money.

## Reading the figures

- **Hours and hours for invoicing**: everything about time (working
  time, planning, budgets in hours, green hours) uses the hours worked.
  Everything about value (logged work, invoicing) uses the hours for
  invoicing where they're filled in.
- **Offered and logged**: budgets count offers in preparation and
  offered ones too; "sold" and "accepted offers total" only count
  accepted offers.
- **Closed projects**: offered amounts no longer count, invoiced amounts
  and logged hours are what remains.
- **Gross margin** is revenue without third party costs. Third party
  costs are deducted once, the larger of invoiced and logged.
- Cancelled invoices never count.

## Working time

- **Annual working time** and the **absence calendar**: see [Absences and
  working time](absences.md).

## Controlling

- **Key data**: revenue per month over the last years, corrected for
  third party costs and accruals, full-time equivalents, a projection of
  the current year and the split of the hours. Last month is final once
  the nightly tasks of the new month have run.
- **Project budget statistics**: per project what was sold, the logged
  work valued at the services' rates, what was invoiced and the
  difference: work not invoiced yet, or invoiced ahead (accruals). Hours
  on services without a rate aren't valued and are listed separately.
- **Projected gross margin**: the planned invoicing of open projects
  which hasn't been invoiced yet, per month, as gross margin. Invoicing
  uses up the oldest projections first; those not invoiced in time stay
  in their month as overdue.
- **Playing bank**: per project the third party costs offered, logged
  and invoiced; a positive difference is money advanced and not passed
  on yet.
- **Open items list**: invoices sent and not paid on a date, with what's
  due when.

## Logbook

- **Hours per customer**: hours per customer and person in a period.
- **Hours per type**: per person external and internal hours against
  the target shares.
- **Planning vs logbook**: planned and logged hours per customer;
  "allocation" is a customer's share of the logged hours divided by its
  share of the planned hours.
- **Green hours**: hours within the budget of orders, beyond it,
  maintenance and internal. The budget is the project's whole budget,
  not the period's, and it says nothing about whether the hours are
  paid.
- **Logging statistics**: how many entries, how promptly they were
  logged and days with too few breaks.

## Deals

With access to deals: **accepted deals** (won value per value type
against the targets), **declined deals** (with the reasons) and the
**deal history** (changes to deals; the person filter is who made the
change).

## Projects

The tiles on a project show the logged hours against the budgeted ones
and, with access to controlling, the logged work and costs, the
budgeted work (some of it not accepted yet), the accepted offers total,
what isn't part of a services invoice yet and the total invoiced.
"Profitability" estimates the project's rate per hour. A **budget
alert** on the project mails its owner once when the logged work
reaches the amount set; changing the amount sets it again.
