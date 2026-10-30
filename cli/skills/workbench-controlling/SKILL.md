---
name: workbench-controlling
description: Summarize the financial state of the agency from Workbench reports using the `wb` CLI, e.g. a monthly controlling summary for the team. Use when the user asks about key figures, gross margin, open invoices, cash flow, accruals, project budgets, utilization or productivity in Workbench, or wants a controlling report.
---

# Controlling summaries from Workbench reports

The `wb` CLI talks to Workbench (see `wb --help`). Most reports require the
controlling feature, squeeze the productivity feature. Reading is enough:
`wb login URL --read`. If a report answers 403, the user lacks the feature;
say so and leave that part out.

Ask which month or period the summary is about and who reads it (the
management, the whole team). Default to the last month.

## 1. Collect the figures

Use `--json` for exact numbers, the tables for a quick look:

    wb reports key-data --month 2026-09 --json        # Gross margin, green hours, deals, open invoices
    wb reports cash-data --json                       # Open and overdue invoices, planned invoicing, accruals
    wb reports budget --json                          # Logged work vs. offers and invoices per project
    wb reports projected-gross-margin --json          # Planned invoicing per month
    wb reports third-party-costs --json               # Costs paid for customers, not invoiced yet
    wb reports hours-per-type --period 2026-09 --json # External vs. internal hours per person
    wb reports green-hours --period 2026-09 --json    # Hours within budgets
    wb reports squeeze --period 2026-09 --json        # Gross margin per person and project
    wb invoices reminders --json                      # Invoices to remind customers of
    wb deals stats --period 2026-09 --json            # Deals won and lost

Periods are years (`2026`), months (`2026-09`), quarters (`2026-Q3`) or
relative (`last-month`, `this-quarter`).

## 2. Read the figures correctly

- Amounts are excl. tax unless a field says `incl_tax`. Gross margin is
  revenue minus third party costs, not profit.
- In cash data, `accepted_offers_not_invoiced.total_excl_tax` is revenue, but
  `not_in_planned_invoicing_excl_tax` and planned invoicing are gross margin.
  Never subtract gross margin from revenue.
- Planned invoicing, accepted offers and work which hasn't been invoiced are
  only available for the current week.
- In the budget report, a positive `delta` is work which hasn't been invoiced
  yet, a negative one accruals. Offered amounts only count for open projects.
- Squeeze for a month may be incomplete until the 9th of the following month
  (`may_be_incomplete`); say so.
- Profitability estimates should rather underestimate than overestimate.

## 3. Write the summary

Lead with the three or four things which need attention, then the figures:

- Gross margin of the period compared to the previous months and the
  projection, full-time equivalents and green hours.
- Liquidity: open and overdue invoices, invoices to remind, planned invoicing
  of the next months.
- Projects needing attention: large positive deltas (work not invoiced),
  projects over their offers, third party costs not passed on.
- Sales: deals won and lost, the funnel.
- Utilization and productivity only if the user asked for it; squeeze shows
  figures per person, be considerate about sharing them with the whole team.

Link projects, invoices and deals with the URLs from the JSON. Don't change
anything in Workbench while preparing a summary.
