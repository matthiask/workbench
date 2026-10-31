# How Workbench computes its figures

This document describes how the reports and key figures of Workbench are
computed: which records count, which fields and dates are used and where the
code lives. German labels are the ones of the user interface
(`conf/locale/de/LC_MESSAGES/django.po`).

Verified against the code in October 2026. When you change how a figure is
computed, update this document in the same commit.

Contents:

1. [Shared definitions](#shared-definitions)
2. [Financial overview](#financial-overview): key data, key data API, cash
   data API, projected gross margin, open items, third party costs
3. [Project budgets](#project-budgets): project budget statistics, project
   key figures, budget transfers, budget alerts
4. [Profitability](#profitability): squeeze, project profitability, labor costs
5. [Time and people](#time-and-people): user statistics, annual working time,
   green hours, hours per customer and type, logging, planning vs. logbook,
   planning capacity
6. [Deals](#deals): accepted and declined deals, deal history
7. [Known inconsistencies](#known-inconsistencies)

## Shared definitions

### Hours and the value of logged work

- **Time** always uses `LoggedHours.hours` (utilization, productivity,
  planning, squeeze's hours, budgets in hours).
- **Value** of logged hours uses `INVOICED_HOURS = Coalesce(invoiced_hours,
  hours)` (`workbench/logbook/models.py`): `invoiced_hours` is optional and
  says what the work is worth if that is more than the time spent.
- **Logbook value ("Logbuch")** = Σ `LoggedCost.cost` + Σ `Service.effort_rate
  × INVOICED_HOURS`. Hours on services without an effort rate are not valued
  (no fallback rate) and are shown separately as hours "ohne Stundensatz"; a
  rate of 0.00 values them at 0. Archived entries are included.
  `workbench/reporting/utils.py:effort_cost_by_project`
- `LoggedCost.third_party_costs` ("Total incl. tax for third-party services")
  is a separate figure, never part of the logbook value. `invoice_service` is
  set once a logged cost is put on a services invoice.

### Offers, services and invoices

- **Service cost** (`ServiceBase.service_cost`, stored on save) = `cost` +
  `effort_hours × effort_rate`; `service_hours = effort_hours`.
  `workbench/services/models.py:ServiceBase.save`
- **Offer total** `total_excl_tax` = Σ `service_cost` of non-optional
  services − discount. **Invoice** `total_excl_tax` = subtotal − discount −
  applied down payments (so down payment invoices count as revenue when
  invoiced and the final invoice deducts them). `total` adds VAT if
  `liable_to_vat`, rounded to 5 cents.
  `workbench/tools/models.py:ModelWithTotal._calculate_total`
- **Invoiced** invoices: `Invoice.objects.invoiced()`, status SENT or PAID.
  This is the *current* status: canceled invoices never count, also not for
  past dates.
- **Outstanding on date D**: invoiced, `invoiced_on ≤ D`, `closed_on` empty
  or after D (`Invoice.objects.outstanding(on=D)`).
- `Invoice.third_party_costs` is entered by hand for statistics; on services
  invoices it is the sum of the invoiced services' third party costs.
- **Budgeted services** (`Service.objects.budgeted()`): not optional, and
  either without offer or on an offer which is neither declined nor a budget
  retainer. Services of offers in preparation or offered **do** count.
- **Budget retainer** offers (`Offer.is_budget_retainer`, "behält Budget
  zurück") are only used for budgeting; their services don't count as budget,
  the actual services are created later.
- **Open projects**: `closed_on` empty. `open(on=D)`: `closed_on` empty or
  after D, and created by D. `external()` leaves out internal projects.
  Figures based on projects (accruals, planned invoicing, offers) leave out
  internal projects in the cash data API; open invoices always include all
  invoices.

### Gross margin and third party costs

`workbench/reporting/squeeze.py`:

| Helper | Computes |
|---|---|
| `third_party_costs(projects)` | per project max(Σ `Invoice.third_party_costs` of invoiced invoices, Σ `LoggedCost.third_party_costs`), all time. Logged costs can't be linked to fixed amount invoices, so adding both would count them twice. |
| `gross_margin_components(projects)` | `offered` = Σ `total_excl_tax` of accepted offers − Σ `Service.third_party_costs` of their services; `projected` = Σ `ProjectedInvoice.gross_margin` (open projects only); `invoiced` = Σ `total_excl_tax` of invoiced invoices − `third_party_costs()`. All time. |
| `hours_components(projects)` | `hours_offered` = Σ `service_hours` of budgeted services; `hours_logged` = Σ `hours`; `hours_logged_budgeted` = Σ `hours` on budgeted services. |
| `relevant_hours(offered, logged, logged_budgeted)` | max(offered, logged_budgeted) + (logged − logged_budgeted): hours on unbudgeted services are added on top, so rates rather underestimate. |
| `BudgetTransfer.objects.adjustments(projects)` | per project Σ transfers in − Σ transfers out. A transfer without target project leaves the source immediately and arrives nowhere. Only money moves, hours stay. |

**Gross margin of a project** (squeeze and the profitability modal):

```
gross_margin = max(max(offered if open else 0, projected, invoiced) + budget_adjustment, 0)
hours        = relevant_hours(hours_offered if open else 0, hours_logged, hours_logged_budgeted)
rate         = gross_margin / hours
```

Offered amounts and hours only count for open projects; for closed projects
the invoiced amount and the logged hours are ground truth.

**Projected invoices** (`ProjectedInvoice.gross_margin`) are gross margin:
invoice total excl. tax minus third party costs. The projected gross margin
not yet invoiced of a project (`workbench/reporting/key_data.py:projected_gross_margin`)
is Σ projections − invoiced gross margin, if positive. It is put on the
projections newest first, each at most its own amount, i.e. invoiced gross
margin uses up the oldest projections first. Projections not invoiced in
time stay in their original month. Projections of zero or less (e.g. credits)
are part of the sum but get nothing allocated.

### Project budget statistics delta

Per project at cutoff date C (`workbench/reporting/project_budget_statistics.py`):
Δ = logbook value (`rendered_on ≤ C`) − Σ `total_excl_tax` of invoiced
invoices (`invoiced_on ≤ C`). Positive deltas are **work not invoiced**
("Nicht verrechnete Arbeit"), negative deltas **accruals** ("Abgrenzungen",
invoiced ahead of work). Several reports reuse these figures, see
[Project budget statistics](#project-budget-statistics-projekt-budgetstatistik).

## Financial overview

### Key data (Kennzahlen)

Web: `/report/key-data/` (URL name `report_key_data`), feature CONTROLLING. Detail modals: `key-data/gross-profit/YYYY.MM/`, `key-data/third-party-costs/YYYY.MM/`.
Answers: how much revenue, corrected for third party costs and accruals, did the agency make per month/year over the last four calendar years, per FTE, and how were hours distributed.

Period: 1 Jan of (current year − 3) to 31 Dec of the current year. `workbench/reporting/views.py:key_data_view`

#### Stat tiles

| Label (DE) | Computation |
|---|---|
| Leistungsstunden in offenen Aufträgen | Σ Service.service_hours of budgeted services on open projects of type `order`. `key_data.py:service_hours_in_open_orders` |
| Erfasste Stunden in offenen Aufträgen | Σ LoggedHours.hours (time, not invoiced_hours; all dates) on services of open `order` projects. `key_data.py:logged_hours_in_open_orders` |
| Total exkl. MwSt aller offenen Rechnungen (EN "Sent invoices total excl. tax") | Σ Invoice.total_excl_tax with status `SENT` (any invoiced_on, any project/none). `key_data.py:sent_invoices_total` |
| Total exkl. MwSt aller fälligen Rechnungen | Σ Invoice.total_excl_tax with status `SENT` and `due_on <= today`. `key_data.py:due_invoices_total` |
| Total exkl. MwSt aller offenen Offerten | Σ Offer.total_excl_tax with status `OFFERED` on open projects (no valid_until check, internal projects not excluded). `key_data.py:open_offers_total`, `OfferQuerySet.offered` |
| Durchschnittliche Anstellungsdauer der aktuellen Mitarbeiter:innen | SQL: per active user Σ (date_until − date_from) over their `Employment` rows (open end `9999-12-31` → current_date); average over users / 365.24, in years, 2 decimals. `workbench/accounts/reporting.py:average_employment_duration` |
| Durchschnittliche Anstellungsdauer aller Mitarbeiter:innen | Same over all users (active or not). |

#### Monthly table (and the two charts)

One row per month (`key_data.py:gross_margin_by_month`); a month is **left out** if gross profit, third party costs, accrual delta and projected gross margin are all zero/empty.

| Column (DE) | Computation |
|---|---|
| Umsatz ("Gross profit") | Σ Invoice.total_excl_tax of invoiced invoices (SENT/PAID) with `invoiced_on` in the month. All types (incl. down payments, credits), all projects incl. internal and invoices without project. `key_data.py:gross_profit_by_month`. Modal lists these invoices. |
| Fremdkosten | Negative: −(Σ LoggedCost.third_party_costs with `rendered_on` in the month, third_party_costs not null, `invoice_service` empty) − (Σ Invoice.third_party_costs of invoiced invoices with `invoiced_on` in the month, type ≠ down payment, third_party_costs ≠ 0). `key_data.py:third_party_costs_by_month`. Modal lists both. |
| Abgrenzungen (muted value) | Accruals at month end: stored `Accruals.accruals` whose `cutoff_date` falls in the month; for the current month computed live with cutoff today. Value = `delta_negative` of project budget statistics over `Project.objects.open(on=cutoff)` (internal projects included). `key_data.py:accruals_by_month`, `reporting/models.py:AccrualsQuerySet.accruals` |
| (delta column, unlabelled) | Accrual of this month − accrual of the previous existing record (any earlier month; the first record is compared to 0). Months without a record: delta 0. |
| Umsatz bereinigt ("Gross margin") | Umsatz + Fremdkosten (negative) + accrual delta. |
| Geplant ("Projected", links to projected gross margin report) | `projected_gross_margin()["monthly_overall"]` for the month: projected gross margin not yet invoiced of all open projects (internal not excluded). Only shown if non-zero. |
| FTE | Σ over all `Employment` rows of percentage/100 × (employment days in month / days in month). `workbench/awt/reporting.py:full_time_equivalents_by_month` |
| Umsatz / FTE ("Margin / FTE") | Umsatz bereinigt / FTE (empty if FTE 0). |

**Year rows**: Σ of the displayed months for Umsatz, Fremdkosten, accrual deltas, Umsatz bereinigt, Geplant; FTE = arithmetic mean of the FTE of the displayed months only; Umsatz/FTE = year gross margin / mean FTE. `views.py:key_data_view`

**Hochrechnung row** (current year extrapolation), factor f = 365.24 / (1 + days since 1 Jan):
- Umsatz: year Umsatz × f
- Umsatz bereinigt: year gross margin × f
- Geplant column: year gross margin × f + Σ projected gross margin of the current year's months
- Umsatz / FTE: (year gross margin × f + projected) / mean FTE of the year

**Chart "Umsatz minus Fremdkosten minus Abgrenzungen"**: Umsatz bereinigt per calendar month; current year as bars plus the current year's projected gross margin as an extra bar series ("geplanter Umsatz"), the three earlier years as lines. `views.py:_years_chart`
**Chart "… pro FTE"**: per quarter, Σ of the monthly Umsatz/FTE values (months not displayed contribute 0); current year bars, earlier years lines.

#### Hours distribution (Stundenverteilung chart + table)

From `workbench/reporting/green_hours.py:green_hours_by_month` (SQL), all logged hours of all users, by month of `rendered_on`:
- Total = Σ LoggedHours.hours in month.
- Profitabel = Σ hours on `order` projects × project factor; factor = (Σ budgeted service_hours of the project, lifetime) / (Σ logged hours of the project, lifetime) if < 1, else 1. Budgeted here = not optional and (no offer or offer not declined and not budget retainer).
- Wartung = Σ hours on `maintenance` projects. Intern = Σ hours on `internal` projects.
- Überzogen = Total − Profitabel − Wartung − Intern.
- grün % = 100 × (Profitabel + Wartung) / Total, rounded to integer. Year row: sums of months, same formula. Percent columns next to each figure: share of total.
- Chart: monthly shares in % of total.

#### Caveats from code
- Accruals are snapshots: the fairy tasks recompute (`update_or_create`) the stored accruals of every month-end of the last two years on each run (`reporting/tasks.py:create_accruals_for_last_month`), with current data (current invoice status, current project types). Older stored records stay as they were.
- Projections not invoiced in time stay in their original month (AGENTS.md; `projected_gross_margin`).

---

### Key data API (Kennzahlen, JSON)

`GET /api/reports/key-data/?month=YYYY-MM` (also `/api/key-data/`, hidden). Auth: static `ReportingToken` (settings.KEY_DATA_API_TOKEN) or user with CONTROLLING. Default month: last month. Decimals as floats (`jsonable()`). `workbench/reporting/api.py:key_data`, `workbench/reporting/key_data_api.py:key_data_for_month`
Answers: the key figures of one month for integrations.

| Field | Computation |
|---|---|
| `gross_margin` | "Umsatz bereinigt" of the month exactly as in the web view (0.00 if the month row is left out). |
| `green_hours_percentage` | grün % of the month (null if no hours). |
| `previous_months[3]` | For each of the 3 preceding months: `green_hours_percentage`, `canceled_invoices_total_excl_tax`. |
| `open_invoices_total_excl_tax` | Σ total_excl_tax of invoices outstanding on the last day of the month (current status: later canceled ones excluded). |
| `canceled_invoices_total_excl_tax` | Σ total_excl_tax of invoices with status `CANCELED` and `closed_on` in the month. |
| `accruals` | Stored `Accruals` with `cutoff_date` = last day of month, else computed live (`delta_negative`, internal projects included, with today's data). |
| `full_time_equivalents` | FTE of the month (see above). |
| `squeeze_gross_margin` | `squeeze_data(month)["totals"]["gross_margin"]` (see squeeze documentation). |
| `deals_funnel` | Open deals as of **today** (not the requested month), Σ Deal.value: `high_probability_next_4_weeks` (HIGH, decision_expected_on − today ≤ 28 days, overdue included), `_next_12_weeks` (≤ 84 days), `_later` (later or no date), `normal_probability` (NORMAL). LOW/UNKNOWN left out. `key_data_api.py:deals_funnel`, `templatetags/workbench.py:deal_group` |
| `accepted_deals` | Deals with status ACCEPTED and `closed_on` in the month: id, title, customer name, value, closed_on. |
| `month`, `generated_at` | Month string, ISO timestamp. |

---

### Cash data API (no web UI label)

`GET /api/reports/cash-data/?date=YYYY-MM-DD` (also `/api/cash-data/`, hidden). Auth: `ReportingToken` or CONTROLLING. Default today. Floats via `jsonable()`. `workbench/reporting/cash_data_api.py:cash_data`
Answers: what money is owed to the agency and what is expected to be invoiced, as of a date.

`is_current` = date ≥ Monday of the current week. Cutoff = max(date, today) if current, else date. Projections/offers/work-not-invoiced are only returned when current (null otherwise) because they aren't versioned.

| Field | Computation |
|---|---|
| `currency` | `settings.WORKBENCH.CURRENCY` |
| `open_invoices.total_excl_tax` / `total_incl_tax` | Σ total_excl_tax / Σ total of invoices outstanding on cutoff (all invoices incl. internal/no project). |
| `open_invoices.overdue_incl_tax` | Σ total of those with `due_on < cutoff`. |
| `receivables_by_due_week[]` | Same invoices grouped by ISO year/week of `due_on` (fallback `invoiced_on`): `amount_excl_tax`, `amount_incl_tax`; empty weeks dropped; past weeks included. |
| `accruals` | `delta_negative` of project budget statistics over `Project.objects.open(on=cutoff).external()` at cutoff (negative; internal projects excluded, always computed live). |
| `planned_invoicing_by_month[]` | `monthly_overall` of projected gross margin not yet invoiced of open **external** projects, from the month of `date`, at least 7 months, extended to the last month with projections. `amount_excl_tax` is gross margin (third party costs not included). |
| `planned_invoicing_overdue_excl_tax` | Σ `monthly_overall` of months before the month of `date`. |
| `accepted_offers_not_invoiced.total_excl_tax` | Revenue: Σ over open external projects of max(Σ accepted Offer.total_excl_tax − Σ invoiced Invoice.total_excl_tax, 0). Budget retainer offers included (`Offer.objects.accepted()`). |
| `accepted_offers_not_invoiced.not_in_planned_invoicing_excl_tax` | Gross margin: Σ over the same projects of max(max(offered GM − invoiced GM, 0) − projected-not-invoiced delta of the project, 0). |
| `work_not_invoiced.total_excl_tax` | `delta_positive` (logged costs + effort cost − invoiced, positive projects only) of open external projects at cutoff. |
| `work_not_invoiced.in_planned_invoicing_excl_tax` | "davon geplant" of the [project budget statistics](#project-budget-statistics-projekt-budgetstatistik). |
| `work_not_invoiced.beyond_offers_excl_tax` | "davon über Offerte" of the project budget statistics; doesn't overlap with the planned part. |

Caveats from code: "The split into planned invoicing is an approximation (rates vs. gross margin)"; figures based on projects leave out internal projects, open invoices include all invoices; "Dates in the current week are evaluated at the time of the request so that invoices paid since monday do not show up as open anymore."

---

### Projected gross margin (geplanter Umsatz)

Web: `/report/projected-gross-margin/` (`report_projected_gross_margin`), CONTROLLING. API: `GET /api/reports/projected-gross-margin/` (CONTROLLING). `workbench/reporting/views.py:projected_gross_margin`, `key_data.py:projected_gross_margin`
Answers: which projected invoicing (as gross margin) of open projects has not been invoiced yet, and in which month it is planned.

Projects: all open projects (internal not excluded) with at least one ProjectedInvoice and delta > 0.

| Column (DE) | Computation |
|---|---|
| Geplant ("Projected") | Σ ProjectedInvoice.gross_margin of the project (all dates). |
| Umsatz bereinigt ("gross margin") | Invoiced gross margin (all invoiced invoices, all dates, minus max(invoice TPC, logged TPC)). |
| Delta | Geplant − Umsatz bereinigt (API: `not_invoiced`). |
| Month columns | Delta allocated to the projections newest-first (see definitions), summed per month of `ProjectedInvoice.invoiced_on`. Only months with any allocation are shown. |
| Total row | `monthly_overall` per month. |

Sorting (web): by the list of monthly values descending (i.e. by the earliest month's amount first). API: by delta descending.

---

### Open items list (Offene-Posten-Liste)

Web: `/report/open-items-list/` (`report_open_items_list`), CONTROLLING, XLSX export. API: `GET /api/reports/open-items/?date=` (CONTROLLING). `views.py:OpenItemsForm.open_items_list`
Answers: which invoices were sent but not paid on the cutoff date (Stichtag, default today).

- List: invoices outstanding on the cutoff date (status SENT/PAID now, invoiced_on ≤ cutoff, closed_on > cutoff or empty), ordered by invoiced_on. Columns: Rechnung, Verrechnet am, Total exkl. MwSt (`total_excl_tax`), Total (`total`, incl. tax).
- Tiles "Total exkl. MwSt" / "Total": Σ total_excl_tax / Σ total of the list.
- "Fällig in Kalenderwoche": per Monday of the week of `due_on` (missing due_on → current week via `monday(None)`), Σ total_excl_tax and Σ total.
- Note: invoices canceled after the cutoff date are missing for past cutoff dates (status is current).

---

### Third party costs ("Bank spielen" / Playing bank)

Web: `/report/playing-bank/` (URL name `report_third_party_costs`, menu "Bank spielen"), CONTROLLING. API: `GET /api/reports/third-party-costs/?this_year=` (CONTROLLING). `workbench/reporting/third_party_costs.py:playing_bank`, `views.py:PlayingBankForm`
Answers: per project, how much third party costs the agency has advanced (logged) vs. passed on to customers (invoiced).

Project filter: "Offen" (default: open projects) or "Immer noch offen oder geschlossen im laufenden Jahr" (closed_on empty or ≥ 1 Jan this year). All project types. Only projects with any of the three sums are listed.

| Column (DE) | Computation |
|---|---|
| Offeriert | Σ Service.third_party_costs (≠ 0) of **all** services of the project (no offer status / optional filter). |
| Erfasst (Vergangenheit) | Σ LoggedCost.third_party_costs (≠ 0) with rendered_on ≤ today (linked to invoice services or not). |
| Erfasst (Zukunft) | Same with rendered_on > today. |
| Verrechnet | Σ Invoice.third_party_costs (≠ 0) of invoiced invoices (SENT/PAID) with a project; all types incl. down payments. |
| Delta | (Erfasst past + future) − Verrechnet; positive = not yet passed on. |
| Header totals | Σ of each column; Delta header shows Σ negative deltas (API `total_invoiced_too_much`) and Σ positive deltas (`total_not_invoiced`). |

Sorting: web by delta ascending; API by delta descending.

## Project budgets

### Project budget statistics (Projekt-Budgetstatistik)

- Web: `report_project_budget_statistics` (`/report/project-budget-statistics/`, XLSX export via `?export=xlsx`), feature **CONTROLLING** (`controlling_only`). API: `GET /api/reports/budget/` (`auth=CONTROLLING`), params `date`, `owned_by` (short name or `inactive`), `internal`, `closed`, `filter` (`no-invoices`, `maintenance`, `old-projects`, `no-projected-gross-margin`). The campaign page reuses the table (`Campaign.statistics`, without discount/projection columns). Accruals snapshots and budget alerts reuse the function.
- Answers: per project, how much work (valued at effort rates) has been logged vs. what was sold and what was invoiced, i.e. which work is not invoiced yet and where we invoiced ahead (accruals).

**Project selection** (`workbench/reporting/views.py:ProjectBudgetStatisticsForm.queryset`): default = projects open on the cutoff date (`closed_on IS NULL or closed_on > date`, `created_at <= date`); `closed` = projects closed during the last 366 days (cutoff still applied to logbook/invoices). Internal projects are excluded unless `internal` (then only internal ones). Cutoff date defaults to today.

**Per-project figures** (`workbench/reporting/project_budget_statistics.py:project_budget_statistics`):

| Label (DE) | Key | Formula |
|---|---|---|
| verkauft (tooltip "Offeriert und akzeptiert") | `sold` | Σ `Offer.total_excl_tax` of offers with status ACCEPTED and `is_budget_retainer=False` (discount already deducted; optional services not in total) **+ net budget transfers** (`BudgetTransfer.objects.adjustments`). No cutoff date filter on offers or transfers. |
| Rabatt (report only) | `discount` | −Σ `Offer.discount` of offers **not declined** (incl. in preparation/offered) and not budget retainers. Shown as a negative number. No cutoff. |
| Logbuch | `logbook` | `cost` + `effort_cost` (see building blocks), entries with `rendered_on <= cutoff`. |
| (hidden in table, API/XLSX) | `cost` | Σ `LoggedCost.cost`, `rendered_on <= cutoff` |
| (hidden, API) | `effort_cost` | Σ `effort_rate × INVOICED_HOURS`, `rendered_on <= cutoff`, rate NULL skipped |
| "(+x h)" ohne Stundensatz | `effort_hours_with_rate_undefined` | Σ `hours` on services with `effort_rate IS NULL`, `rendered_on <= cutoff` |
| Fremdkosten | `third_party_costs` | Σ `LoggedCost.third_party_costs` (not NULL) with `invoice_service IS NULL` (not yet put on a services invoice), `rendered_on <= cutoff`. Display only, not deducted from anything. |
| Verrechnet | `invoiced` | Σ `Invoice.total_excl_tax`, status SENT/PAID, `invoiced_on <= cutoff`. Third party costs on invoices are **not** deducted. |
| Leistungsstunden: "logged / budgeted" | `hours` / `service_hours` | `hours` = Σ `LoggedHours.hours` (all services, incl. declined/optional/rate-less), `rendered_on <= cutoff`; `service_hours` = Σ `service_hours` of budgeted services (no cutoff). |
| Δ | `delta` | `logbook − invoiced` (`cost + effort_cost − invoiced`). Positive = work not invoiced, negative = accruals. |
| geplanter Umsatz (report only) | `projected_gross_margin` | Σ `ProjectedInvoice.gross_margin`, **open projects only** (`closed_on IS NULL` today), all dates. |
| column headed with cutoff date "dd.mm." | `projected_gross_margin_on_cutoff_date` | same, only projections with `invoiced_on <= cutoff`. |

Sorted by `delta` descending (closed-filter: by `closed_on` descending).

**Overall figures (tiles + total row):**

| Label (DE) | Key | Formula |
|---|---|---|
| verkauft, Logbuch, Verrechnet, Rabatt, Fremdkosten, hours, … | same keys | plain sum of the per-project values |
| Nicht verrechnete Arbeit | `delta_positive` | Σ `delta` of projects with `delta > 0` |
| Abgrenzungen | `delta_negative` | Σ `delta` of projects with `delta < 0` (negative number) |
| davon geplant (tooltip "Durch noch nicht verrechneten geplanten Umsatz gedeckt (Näherung)") | `delta_planned` | Σ over projects with `delta > 0` of `planned = min(delta, P, max(P − I, 0))`, `P` = `projected_gross_margin` (all projections, open projects only), `I` = invoiced gross margin from `gross_margin_components()["invoiced"]` = all SENT/PAID invoices **without cutoff** − `max(third party costs on invoices, logged third party costs)` (`workbench/reporting/squeeze.py:third_party_costs`). |
| davon über Offerte (tooltip "Mehr erfasst als offeriert und verrechnet, z.B. Stunden über der Offerte und Rabatte") | `delta_beyond_offer` | Σ over projects with `delta > 0` **and `sold != 0`** of `min(max(logbook − max(sold, invoiced), 0), delta − planned)`: the rest not covered by planned invoicing which was logged beyond the offers. Projects without any sold amount contribute nothing. |

The two "davon" figures don't overlap: planned invoicing comes first because it may cover additional work which has been agreed, "über Offerte" is taken from the rest. Together they are at most `delta_positive`.

**Worked example** (one open project, cutoff today):
- Accepted offer: subtotal 10,500, discount 500 → total 10,000. Budget transfer in from another project: +1,000. → **verkauft 11,000**, Rabatt −500.
- Logged 100 h at effort rate 120 (invoiced_hours empty) = 12,000; 5 h on a service without rate; logged cost 800 with third party costs 600, not yet invoiced. → **Logbuch 12,800 (+5 h)**, Fremdkosten 600.
- Invoiced (sent): 8,000. → **Δ = 12,800 − 8,000 = +4,800** → counts toward "Nicht verrechnete Arbeit".
- Projected gross margin 9,000; invoiced GM = 8,000 − max(0, 600) = 7,400; planned = max(9,000 − 7,400, 0) = 1,600 → davon geplant = min(4,800, 1,600) = **1,600**.
- davon über Offerte = min(max(12,800 − max(11,000, 8,000), 0), 4,800 − 1,600) = **1,800**.
- If instead 14,000 had been invoiced: Δ = −1,200 → counted in **Abgrenzungen** −1,200, nothing in the "davon" figures.

**Caveats (from code comments/docs):**
- "davon geplant" mixes logbook values (effort rates) with gross margin and "is only an approximation" (comment at `project_budget_statistics.py:132-136`).
- Hours on services without effort rate are not valued (`effort_cost_by_project` docstring); the logbook understates such projects.
- Budget transfers: "Budget which was invoiced on one project but is worked off on another (or reserved for that) belongs to the project which does the work." Only money moves; hours stay where they were logged.
- Figures use the logbook value at effort rates, i.e. revenue-like, not cost/gross margin; third party costs are neither deducted from `logbook` nor from `invoiced`.

**Accruals snapshots** (`workbench/reporting/models.py:AccrualsQuerySet.accruals`): `delta_negative` of `Project.objects.open(on=cutoff)` (internal projects **included**) on each month end; `create_accruals_for_last_month()` (fairy tasks) recomputes the last ~24 month ends.

**Campaign page** (`Campaign.statistics`): same function over all projects of the campaign (open and closed, internal included, cutoff today), plus `gross_margin_per_hour` = Σ invoiced gross margin (`gross_margin_components`) / Σ `hours`.

Code: `workbench/reporting/project_budget_statistics.py:project_budget_statistics`, `workbench/reporting/views.py:project_budget_statistics_view`, `workbench/reporting/api.py:budget`, `workbench/tools/xlsx.py:project_budget_statistics`, `workbench/templates/reporting/project_budget_statistics.html`, `workbench/templates/reporting/_budget_statistics_table.html`.

---

### Project key figures (project detail `.wb-stats`)

- `projects_project_detail`, `workbench/templates/projects/project_detail.html`; "Stunden" and "Kosten" tiles visible to everyone, the rest requires **CONTROLLING**. No cutoff date: everything as of now, archived entries included unless stated.
- Answers: how far the project's logged hours and logged value have progressed against its budgeted services and accepted offers, and how much has been invoiced.

Source: `Project.grouped_services` (dict, `workbench/projects/models.py:Project.grouped_services`), `Project.not_archived_total`, `Project.project_invoices_total_excl_tax`.

| Label (DE) | Template value | Formula |
|---|---|---|
| Stunden: "logged / budgeted" | `gs.logged_hours` / `gs.service_hours` | Σ `LoggedHours.hours` over all services of the project / Σ `service_hours` of services that are not declined, not optional, not on a budget retainer offer (same as `budgeted()`). |
| Kosten: "logged / budgeted" (only if either ≠ 0) | `gs.logged_cost` / `gs.service_cost` | Σ `LoggedCost.cost` / Σ `Service.cost` (fixed cost part only, no effort) of budgeted services. |
| Erfasste Kosten (+x h ohne Stundensatz) | `gs.total_logged_cost` | Σ `LoggedCost.cost` + Σ `effort_rate × INVOICED_HOURS` per service with a rate; hours on rate-less services shown as `total_logged_hours_rate_undefined`. Same as report "Logbuch" without cutoff. Bar against `total_service_cost`. |
| Leistungskosten (+x h ohne Stundensatz) | `gs.total_service_cost` | Σ `service_cost` of budgeted services (all offer statuses except declined; incl. services without offer). Rate-less hours: Σ `service_hours` of rate-less services not declined, not optional and not retainer. |
| Noch nicht akzeptiert (note) | `gs.not_accepted_service_cost` | `total_service_cost − accepted_offers_service_cost`, where the latter = Σ `service_cost` of budgeted services on ACCEPTED offers. So it covers services without offer **and** services on offers in preparation / offered. |
| Zurückbehaltung von Budget (only if any offer `is_budget_retainer`) | `gs.budget_retainment` | `budget_retainer_total − total_service_cost`; `budget_retainer_total` = Σ `total_excl_tax` of **accepted** retainer offers. Note: "<retainer total> verkauft, <total_service_cost> freigegeben (inkl. <discount> Rabatt)" with discount = Σ discount of accepted retainer offers. |
| Akzeptiertes Offertentotal (if no retainer offers) | `gs.accepted_offers_total_excl_tax` | Σ `total_excl_tax` of ACCEPTED offers; note "includes discount of" Σ discount of accepted offers. Budget transfers are **not** included here. |
| Nicht archiviert | `project.not_archived_total.total` | Σ `LoggedCost.cost` + effort value (`effort_cost_by_project`) of entries with `archived_at IS NULL`; plus rate-less hours. |
| Total verrechnet exkl. MwSt | `project.project_invoices_total_excl_tax` | Σ `total_excl_tax` of the project's SENT/PAID invoices (all dates). |
| Budgetwarnung ab X – gesendet am … | `project.budget_alert_at`, `budget_alert_sent_at` | see Budget alerts |

Warning (retainers): if `budget_retainment > 0` and `total_logged_cost > 1.1 × total_service_cost` → "Dieses Projekt verwendet Offerten, welche das Budget zurückhalten. Die aufgeschriebenen Kosten sind wesentlich höher als die freigegebenen Kosten."

Per offer (service list): `service_hours`, `logged_hours`, `service_cost` (Σ `Service.cost`), `logged_cost` (Σ `LoggedCost.cost`) per offer, budgeted services only for the service side.

**Worked example:** services A (20 h × 150 = 3,000, accepted offer), B (10 h × 150 = 1,500, offer still "offered"), C (optional, 5 h, accepted offer). Logged 25 h × 150 + 200 cost = 3,950. → Stunden 25 / 30; Leistungskosten 4,500, Noch nicht akzeptiert 1,500; Erfasste Kosten 3,950; Akzeptiertes Offertentotal 3,000 (if no discount).

Caveats: Budget retainer offers hold budget, real services are added later ("services have to be created later when rendering actual work", `Offer.is_budget_retainer` help text); retainment is the part of the retainer not yet released into services. (Unclear: whether released services are expected to sit on accepted offers; the report's `sold` excludes retainer offers, so a retainer project only shows "sold" for later accepted non-retainer offers.)

---

### Budget transfers (Budgetverschiebung)

- Created from the project's "New" dropdown (`projects_project_createbudgettransfer`), edited/deleted via `projects_budgettransfer_update/delete`. Requires `CONTROLLING` (the form shows the project's gross margin). Fields: von Projekt, auf Projekt (optional), title, amount, notes. No date.
- Answers: which share of a project's invoiced budget is worked off on (or reserved for) another project.

Formula (`workbench/projects/models.py:BudgetTransferQuerySet.adjustments`): per transfer, `from_project −= amount` immediately; `to_project += amount` only if set (otherwise "reserved", money has left but arrived nowhere).

Used in:
- Report `sold` += adjustment (all transfers, no cutoff date).
- Squeeze / `project_gross_margin`: `gross_margin = max(gross_margin + adjustment, 0)` (`workbench/reporting/squeeze.py:project_gross_margin`, and the bulk squeeze).
- Form: "Available" = `project_gross_margin(project)["gross_margin"]` (+ the edited transfer's own amount); larger amounts only give a warning "… leaves … with a negative budget" (`workbench/projects/forms.py:BudgetTransferForm`).
- Not used in project detail tiles (`accepted_offers_total_excl_tax`), nor in the budget alert's cost-cap help text, nor in `gross_margin_components`.

Example: Project A sold 50,000; transfer 10,000 to B → A sold 40,000, B sold +10,000. With `to_project` empty: A 40,000, nobody +10,000.

---

### Budget alerts (Budgetwarnung)

- Field `Project.budget_alert_at` ("Mail senden, wenn die aufgeschriebenen Kosten erreichen"), sent by `workbench/projects/tasks.py:send_budget_alerts` from `fairy_tasks`.
- Answers: has a project's logged value reached the threshold its owner configured?

Logic:
- Candidates: open projects (`closed_on IS NULL`) with `budget_alert_at` set and `budget_alert_sent_at` empty (internal projects included).
- Trigger: `project_budget_statistics(projects)` with cutoff today; alert if `logbook >= budget_alert_at` (logbook = logged cost + effort value incl. INVOICED_HOURS; rate-less hours not counted).
- One mail per owner listing project, URL, Logbuch, Warnen ab, Verkauft (= report `sold`, incl. budget transfers). Then `budget_alert_sent_at = now`.
- Re-armed when `budget_alert_at` changes (`Project.save` clears `budget_alert_sent_at`).
- Form help text "Cost cap" = Σ `total_excl_tax` of accepted non-retainer offers, with 75/80/90 % shortcuts (`workbench/projects/forms.py`, comment says "Same definition as 'sold'", but transfers are not included).

## Profitability

### Squeeze (Squeeze)

Web: `report_squeeze` (`/report/squeeze/`, `productivity_only`, i.e. feature
`PRODUCTIVITY`), XLSX via `?export=xlsx`; API `GET /api/reports/squeeze/`
(`user_auth(feature=FEATURES.PRODUCTIVITY)`); management command `squeeze`;
`totals.gross_margin` is also `squeeze_gross_margin` in the key data API
(`workbench/reporting/key_data_api.py`). Default period: last month
(`LastMonthDateRangeFilterForm` / `last_month_range()`).

Answers: how much (estimated, all-time) project gross margin each person
"earned" through the hours they logged in the period, compared with what is
expected of them.

Warning shown if today < 9th of the month after the period end ("Die Rechnungen
für den gewählten Zeitraum sind möglicherweise noch nicht vollständig
(Stichtag: …)"); the API returns the same as `may_be_incomplete`
(`workbench/reporting/views.py:squeeze_view`, `workbench/reporting/api.py:squeeze_api`).

#### Which projects

Every project with at least one `LoggedHours` row with `rendered_on` in the
period (any project type, including internal projects, which usually have
gross margin 0). Gross margin and hours of these projects are **all-time**.

#### Split of gross margin between people (period slice)

Per project (`squeeze_data`):

```
weight(row)          = hours × COALESCE(NULLIF(service.effort_rate, 0.00), 150)
hours_in_range_total = Σ hours logged on the project in the period (all people)
period_margin        = hours_in_range_total / hours × gross_margin          (0 if hours == 0)
person's margin      = Σ weight(person, period) / Σ weight(all, period) × period_margin
person's rate        = person's margin / person's hours on the project
hours_rate_unknown   = person's period hours on services with effort_rate NULL or 0
```

The total attributed per project equals the hours-only slice; the rate
weighting only shifts it between people. Since the slice is proportional to
hours, the project's period rate always equals its all-time rate.

**Worked example.** Project, open, gross margin 60'000, relevant hours 400 →
rate 150/h. In the period Anna logs 20h on a service at 200/h (weight 4'000),
Ben 20h on a service at 0.00/h (weight 20 × 150 = 3'000, counted as "ohne
Stundensatz").
`period_margin = 40 / 400 × 60'000 = 6'000`.
Anna: `4'000 / 7'000 × 6'000 = 3'428.57` (171.43/h); Ben: `3'000 / 7'000 ×
6'000 = 2'571.43` (128.57/h).

#### Projects table ("Projekte"), sorted by period gross margin desc

| UI label (de) | Computation |
|---|---|
| Projekt | project |
| Offeriert | `offered` (accepted offers − their service third party costs); 0 for closed projects |
| Geplant *offen* | `projected` = Σ `ProjectedInvoice.gross_margin`, open projects only |
| Verrechnet | `invoiced` = SENT/PAID invoices `total_excl_tax` − `third_party_costs()` (max of invoice vs. logged third party costs) |
| Umsatz bereinigt *geschätzt* | `gross_margin` (formula above; incl. budget transfers, floored at 0) |
| Relevante Stunden | `hours` = `relevant_hours(...)` (offered hours only for open projects) |
| Ansatz | `gross_margin / hours`; red if < 150 |
| Stunden im Zeitraum | Σ hours of all people in the period |
| Deckungsbeitrag im Zeitraum | Σ attributed person margins = `period_margin`; links to the per-person modal |
| Total row | Σ period hours, Σ period gross margin |

Per-project modal ("Aufschlüsselung nach Person"): header Umsatz bereinigt /
Stunden (= relevant hours) / Ansatz; per person Stunden, Ohne Stundensatz
(`hours_rate_unknown`), Umsatz bereinigt (person margin), Ansatz (person
rate, red < 150); footer shows period totals and the project rate. Note "Stunden
ohne Stundensatz: Standard von 150/h angewendet" if any.

XLSX additionally: offered hours (only open projects), logged hours (all
time), period rate (`gross_margin_in_range / hours_in_range`), hours at default
rate, and per user hours / gross margin / rate / hours at default rate.

#### Users table ("Mitarbeiter:innen"), sorted by Delta desc

Everyone who logged hours in the period (also only on internal projects).

| UI label (de) | Computation |
|---|---|
| Mitarbeiter:in | user |
| Fachbereich | `specialist_field.name`, else "<unbekannt>" |
| Anstellungsverhältnis % | average of `employment_percentages()[user][month]` over the months of the period, weighted with the days of each month in the period; monthly values pro-rate partial-month employments by calendar days (`workbench/awt/reporting.py:employment_percentages`) |
| Abwesenheitstage | Σ absence days in the period (see below) |
| Stunden | `hours_in_range` = Σ all hours the person logged in the period on **all** projects (internal ones too) |
| Ansatz | `gross_margin / hours_in_range` (so internal hours dilute it) |
| Umsatz bereinigt | Σ the person's attributed period margins over all projects; links to the per-project modal |
| Extern % | `100 × external_hours / total_hours` (external = hours on non-internal projects, `workbench/projects/reporting.py:hours_per_type`) |
| Richtwert extern % | `profitable_percentage = 100 − Σ InternalTypeUser.percentage` (per-user override, else the internal type's default percentage) |
| Δ ext. % | `Extern % − Richtwert extern %`, red if < 0 |
| Erwarteter Ansatz | `specialist_field.expected_hourly_rate`, else 150 |
| Erwarteter Deckungsbeitrag | `expected_rate × 8 × (working_days − absence_days) × profitable% / 100 × employment% / 100`, with `working_days = (date_until − date_from + 1) × 250 / 365.24` |
| Delta | `Umsatz bereinigt − Erwarteter Deckungsbeitrag`, red if < 0 |
| Total row | Σ employment %, Σ absence days, Σ hours, total rate = Σ margin / Σ hours, Σ margin, total Extern % from `hours_per_type` totals, Σ expected margin, Σ delta |

Absence days: absences overlapping the period (or without `ends_on` starting in
it) with reason vacation, paid, school, or correction with `days > 0`
(sickness and other are **not** deducted). Each absence's `days` is spread
evenly over its calendar days, and those within the period are counted.

API/XLSX only: `invoiced_per_external_hour = gross_margin / hours_in_range /
(1 − internal_hours / total_hours)` (≈ gross margin per external hour), 0
without external hours.

#### Specialist fields ("Fachbereiche"), sorted by rate desc

Σ over the users of the field: Stunden (`hours_in_range`), Umsatz bereinigt,
Ansatz = Σ margin / Σ hours, Extern % = `100 × Σ external / Σ total hours`.
Users without a field are grouped as "<unbekannt>".

#### Organizations ("Organisationen"), sorted by rate desc

Per `project.customer`: Σ of the person contributions (margin, period hours) of
its projects; Ansatz = margin / hours. Internal projects count with their
(usually 0) margin under the own organization.

#### Caveats from the code

- All figures are estimates that should rather underestimate (`relevant_hours`
  docstring, profitability modal "Annahmen").
- Gross margin and relevant hours are all-time, only the slice is per period;
  invoices of the period may be incomplete until the 9th of the next month.
- A rate of 0.00 means "paid elsewhere (package price)", not worthless, hence
  the 150 fallback in the weight.
- Budget transfers move margin so that the source project doesn't get "too high
  a rate and the target project none".
- Third party costs: larger of invoiced vs. logged, because logged costs can't
  be linked to fixed amount invoices and adding both would double count.

Code: `workbench/reporting/squeeze.py:squeeze_data`, `:build_xlsx`,
`:gross_margin_components`, `:hours_components`, `:third_party_costs`,
`:relevant_hours`, `:working_days_estimation`;
`workbench/reporting/views.py:squeeze_view`;
`workbench/templates/reporting/squeeze.html`;
`workbench/reporting/api.py:squeeze_api`;
`workbench/projects/reporting.py:hours_per_type`;
`workbench/awt/reporting.py:employment_percentages`.

---

### Project profitability modal (Rentabilität)

URL `projects_project_profitability` (`/projects/<pk>/profitability/`,
`controlling_only`, button shown with feature `CONTROLLING`). The same dict
also feeds the project detail page (warnings about projected invoices) and
`gross_margin` in `GET /api/projects/stats/` (`CONTROLLING`, fields
gross_margin, rate, offered, projected, invoiced, quantized to 0.01).

Answers: how profitable is this single project over its whole life, overall
and counting accepted offers only.

`project_gross_margin(project)`:

| UI label (de) | Computation |
|---|---|
| **Umsatz bereinigt** section | |
| Akzeptierte Offerten | `offered` (accepted offers − their service third party costs); shown also for closed projects with "(bei geschlossenen Projekten nicht verwendet)" |
| Geplante Rechnungen | `projected` (0 for closed projects) |
| Verrechnet | `invoiced` (SENT/PAID − `third_party_costs()`) |
| Budgetverschiebungen | `budget_adjustment` (only shown if ≠ 0) |
| Umsatz bereinigt | `max(max(offered if open else 0, projected, invoiced) + budget_adjustment, 0)` |
| **Stunden** section | |
| Leistungsstunden | `hours_offered` = budgeted service hours (displayed for closed projects too, but not used there) |
| Erfasste Stunden auf diesen Leistungen | `hours_logged_budgeted` |
| Erfasste Stunden auf anderen Leistungen | `hours_logged − hours_logged_budgeted` |
| Relevante Stunden | `relevant_hours(hours_offered if open else 0, hours_logged, hours_logged_budgeted)` |
| Ansatz (overall rate) | `gross_margin / hours` |
| **Nur akzeptierte Offerten** (shown if `offered` ≠ 0) | |
| Umsatz bereinigt | `offered` (no budget adjustment, no max(); also for closed projects) |
| Offerierte Stunden | `hours_accepted_offered` = Σ `service_hours` of budgeted services of accepted offers |
| Erfasste Stunden | `hours_accepted_logged` = Σ hours logged on services of accepted offers (optional services included) |
| Relevante Stunden | `relevant_hours(hours_accepted_offered, hours_accepted_logged, hours logged on budgeted services of accepted offers)` |
| Ansatz (rate on accepted offers) | `offered / hours_accepted` |

Overall rate vs. accepted-offers rate: the overall rate divides the best
margin estimate by all budgeted hours (offers not yet accepted and services
without offer included, though their amount is not) plus unbudgeted logged
hours; the accepted-offers rate uses only accepted offers' amount and hours,
"how profitable the project is if no further offers are accepted and no work
happens outside of the accepted offers" (modal text).

Squeeze uses the same overall rate; it has no accepted-offers rate.

Code: `workbench/reporting/squeeze.py:project_gross_margin`;
`workbench/projects/views.py:ProjectProfitabilityView`, `:ProjectDetailView`;
`workbench/templates/projects/project_profitability.html`;
`workbench/projects/api.py:project_stats`; also used by
`workbench/projects/forms.py` (budget transfer form: "Available" =
`gross_margin + this transfer's current amount`; larger amounts only get a
warning, not an error).

---

### Labor costs (Personalaufwand)

Web: `report_labor_costs` (`/report/labor-costs/`, `labor_costs_only`, i.e.
feature `LABOR_COSTS`). No API, no CLI. Default period: the current week
(Monday–Sunday, `DateRangeFilterForm`). Modals via `?project=<id>`,
`?cost_center=<id>`, `?users=all` (all render `labor_costs_by_user.html`).

Answers: what the hours logged in the period cost in salaries, per cost center
and project, against a rough revenue.

Basis: `LoggedHours` with `rendered_on` in the period, joined to the person's
`Employment` valid on `rendered_on` (`date_from ≤ rendered_on ≤ date_until`),
which supplies `hourly_labor_costs` (HLC) and `green_hours_target` (GHT, both set
or both empty). Uses `hours`, not `invoiced_hours`. Raw SQL in
`LABOR_COSTS_SQL` / `REVENUE_SQL`.

| UI label (de) | Computation |
|---|---|
| Projekt / cost center row ("Keine Kostenstelle definiert" if none) | projects grouped by `project.cost_center`, cost centers ordered by id (none last), projects by Nettopreis desc; cost center rows and Total are sums |
| Stunden | Σ hours in the period |
| Ohne Stundensatz | Σ hours without an employment with HLC on that day |
| Nettopreis | Σ `hours × HLC` |
| Rentabilitätskosten | Σ `hours × HLC × 100 / GHT` (labor cost grossed up for the share of productive "green" hours) |
| Fremdkosten | Σ `LoggedCost.third_party_costs` (not NULL) with `rendered_on` in the period |
| Kosten | `Rentabilitätskosten + Fremdkosten` (template `addf`) |
| Ertrag (tooltip "Stunden mal max(Stundensatz, Personalaufwand)") | Σ `hours × max(COALESCE(HLC,0), COALESCE(service.effort_rate,0))` + Σ `LoggedCost.cost` with `rendered_on` in the period |

User modal ("Personalaufwand"): per user Stunden, Ohne Stundensatz, Nettopreis,
Rentabilitätskosten for the selected project / cost center / everything, plus
a Fremdkosten row and a total row.

Caveats: none in code comments. Hours without HLC add to Stunden but not to
costs; Ertrag values hours at the labor cost if that exceeds the effort rate
(so work at 0.00/h still counts at cost).

Code: `workbench/reporting/labor_costs.py:_labor_costs_by_project_id`,
`:labor_costs_by_cost_center`, `:labor_costs_by_user`;
`workbench/reporting/views.py:labor_costs_view`;
`workbench/templates/reporting/labor_costs.html`,
`workbench/templates/reporting/labor_costs_by_user.html`;
`workbench/awt/models.py:Employment`.

## Time and people

### User statistics (Statistik: "Stunden pro Woche", "Stunden pro Kundschaft")

- Where: `/users/<pk>/statistics/` (`accounts_user_statistics`, `workbench/accounts/views.py:ProfileView`). No feature check, so any user can open any user's page. No API.
- Answers: how many hours a person logged per week over roughly the last half year, by project type and by customer, compared with the expected hours.
- Period: from `monday(today − 180 days)` to the Sunday of the current week. Weeks without hours are kept as 0 (`generate_series`).

| Figure | Computation |
|---|---|
| Stunden pro Woche (bars per project type: Order/Maintenance/Internal, `Project.TYPE_CHOICES`) | `SUM(hours)` of the user's `LoggedHours` grouped by `date_trunc('week', rendered_on)` and `project.type` |
| Erwartet (dashed line, both charts) | `working_time_per_day(Year of user's WTM, year of the week's Monday, default 8.0) × 5 × employment.percentage / 100`. The employment is the one covering the Monday (if several match, the last one by `date_from` wins). The line is 0 without an employment. Holidays and absences are **not** subtracted. |
| Stunden pro Kundschaft | `SUM(hours)` per week and `customer.name` (first line only). The 7 customers with the most hours over the whole period get their own series, and everyone else goes into "Alle anderen". Each label gets `round(100 × customer_hours / all_hours)%`. |

Code: `workbench/accounts/reporting.py:logged_hours`, chart in `workbench/accounts/views.py:ProfileView.get_context_data`.
Productivity in the sense of the `PRODUCTIVITY` feature ("Produktivität") is the squeeze report (`report_squeeze`, `/api/reports/squeeze/`), see [Squeeze](#squeeze-squeeze).

---

### Annual working time (Jahresarbeitszeit)

- Where: web `/report/annual-working-time/` (`awt_year_report`, `workbench/awt/views.py:annual_working_time_view`), with `?year=`, `?user=<id>|active` and `?export=pdf` (one PDF, or a ZIP of PDFs plus an XLSX sheet "Stundensaldo fortlaufend" and a holiday list, `workbench/awt/pdf.py:annual_working_time_pdf`). API: `GET /api/reports/working-time/?year=&user=&all=&weekly=` (`workbench/awt/api.py:working_time`), CLI `wb reports working-time`.
- Access: your own report needs no feature. Other users and everyone (web `active`, API `all`) require `PERSONNEL_ADMINISTRATION`, because the report contains sickness absences. On the web the parameter is silently ignored without the feature and you get your own report; the API answers 403.
- Answers: did the person work their target time this year, counting absences, and how many vacation days are left?

#### Inputs
- `Year` per working time model (WTM) and year: `january…december` = target days for full-time employment ("Soll-Arbeitstage bei 100%"; `create_holidays` fills these with the weekday count) and `working_time_per_day` (wtpd). Years with wtpd ≤ 0 are reported as misconfigured and skipped. Users without a `Year` for their WTM show up as warnings and are left out.
- `Employment`: `date_from`, `date_until` (default `date.max`), `percentage`, `vacation_weeks` (for a full year). Saving an employment cuts the previous one off the day before.
- `Holiday` per WTM: `date`, `fraction` (e.g. 0.25 for Gründonnerstag), `kind` public/company. They are generated by `workbench/awt/holidays.py:get_public_holidays` + `get_zurich_holidays` (Easter by Lichtenberg's formula; Sechseläuten and Knabenschiessen are 0.5) through `workbench/awt/tasks.py:create_holidays` for this year and the next two years.
- `Absence`: `starts_on`, `ends_on` (optional), `days` (working days as entered, not scaled by percentage), `reason`. The reason `other` sets `is_working_time=False`, and those absences don't count ("Only shown for completeness"). Start and end must be in the same year.
- `VacationDaysOverride` per user and year: `absolute` (replaces) or `relative` (adds days).

#### Per month m (all 12 months, summed over the employments in that month)
`partial = calendar days employed in m / calendar days of m` (`monthly_days`, `days_per_month`). `pct = percentage/100`.

| Figure (German label) | Computation |
|---|---|
| Soll-Arbeitstage bei 100% | `Year.<month>`, shown as is |
| Gesetzliche Feiertage / Betriebsferien | `Σ fraction` of the WTM's holidays of that kind on weekdays (Mon–Fri) **within the employment period** (`holiday_days_by_month`), at most one day per date (several holidays on the same day count once). Not scaled by pct. |
| Pensum | `Σ 100 × pct × partial`. The total column is the 12-month average. |
| Verfügbare Ferientage | `Σ vacation_weeks × 5 / 12 × pct × partial`. The total is replaced or adjusted by the override ("Manuell definierte Ferientage"). |
| Sollstunden | `Σ (Year.month × partial − (public + company holiday days in the employment)) × pct × wtpd`. Holidays are not scaled by `partial` because they are already restricted to the employment. |
| Bezogene Ferientage, Krankheitstage, Bezahlter Urlaub, Schulbesuch durch Auszubildende, Arbeitszeit-Korrektur | `Σ absence.days` per reason (`absence_<reason>`) for absences with `starts_on` in the year and `is_working_time`. Absences spanning months are split **by calendar days**: `days × calendar_days_in_month / total_calendar_days`. |
| Korrektur anrechenbarer Ferientage | Vacation absences are processed in `starts_on` order, per month chunk `d`. If `d > remaining` then `correction += remaining − d` (≤ 0), and then `remaining = max(0, remaining − d)`. `remaining` starts at the available vacation days (after the override). Vacation beyond the entitlement doesn't count as working time. |
| Anrechenbare Abwesenheitsstunden | `(vacation + sickness + paid + school + correction + vacation_days_correction) × wtpd` |
| Erfasste Stunden | `Σ LoggedHours.hours` with `rendered_on` in that month |
| Arbeitszeit | `Erfasste Stunden + Anrechenbare Abwesenheitsstunden` |
| Stundensaldo pro Monat | `Arbeitszeit − Sollstunden` |
| Stundensaldo fortlaufend | cumulative sum of the monthly balances from January. The total is `Σ` of all 12 months, rounded to 0.1 (`Z1`). |
| Guthaben an Ferientagen | `remaining` after all vacation, if > 0. The display is rounded **up** to 0.01. |
| Bilanz | `Σ monthly balances + wtpd × vacation days credit`. "balance_days" = `Bilanz / wtpd`, rounded up to 0.01. |

Overall tiles at the top (sums over all users shown): Verfügbare Ferientage, Bezogene Ferientage (korrigiert) = `Σ absence_vacation + Σ vacation_days_correction` (the correction is zero or negative), Krankheitstage, plus "Geschätzte X Tage pro 100% und Jahr" = `Σ sickness days / (Σ working time / 250 / 8)` (hard-coded 250 days × 8 h), Bezahlter Urlaub, Schulbesuch, Arbeitszeit-Korrektur, Stundensaldo, Guthaben an Ferientagen and Bilanz.

Vacation planning warning ("Ferienplanung!", `vacation_planning_warnings`, only for active users). It fires if `Σ planned vacation days / available days < 0.5` ("Weniger als die Hälfte…"), or if no vacation absence lasts at least 14 calendar days (`ends_on − starts_on ≥ 13`). The second check is only made if vacation entitlement exists in more than 6 months.

Monthly warning mails (`annual_working_time_warnings`, `workbench/awt/tasks.py:annual_working_time_warnings_mails`) go out on the day the previous month gets locked. They cover active users without `DISABLE_AWT_MONITORING` whose `|running balance at the end of last month| > 40 h`.

#### Weekly view (API `weekly=true` only, `working_time_by_week`)
This view covers January 1 up to today, per Monday-week. Each weekday contributes `target = wtpd × percentage/100 × (1 − min(Σ holiday fractions that day, 1))` per employment that covers it. Hours are logged hours. Absences (`is_working_time`) are spread evenly over the weekdays they span, `days / n_weekdays × wtpd`, and only days ≤ today count. `delta = hours + absences − target`, and `running_delta` is its cumulative sum. There is no vacation correction or credit, and the view uses weekdays instead of `Year.months`.

#### Worked example (made-up)
Assume wtpd = 8 h and March has `Year.march` = 22 days. The person works 80% all year with 5 vacation weeks. There is one public holiday (fraction 1, a Monday) in March, and a 4-day vacation (Tue–Fri of the same week, entered as `days = 4`). The person logged 110 h in March.
- Sollstunden March = (22 × 1 − 1) × 0.8 × 8 = **134.4 h**
- Verfügbare Ferientage per month = 5 × 5 / 12 × 0.8 = 1.667, which makes **20 days** per year
- Anrechenbare Abwesenheitsstunden = 4 × 8 = **32 h** (absence days are full days at wtpd. The person enters 4 days for their week off, which equals 4 × 6.4 h × 5/4)
- Arbeitszeit = 110 + 32 = 142 h. **Stundensaldo pro Monat = 142 − 134.4 = +7.6 h**
- The week view of that week: target = 4 weekdays × 6.4 = 25.6 h, and the 4 vacation days are spread over 5 weekdays = 0.8 days/day × 8 h = 32 h.
- Year end: suppose these were the only vacation days. Then the credit is 16 days, and `Bilanz = Σ monthly balances + 16 × 8 = Σ + 128 h`.

#### Caveats (from code and template)
- "Monthly sums may not be exact: absences spanning month boundaries are split by calendar days, not by working days. The annual total is correct." (template note)
- The employment `partial` factor is calendar days, not working days.
- Future months of the current year already carry their full target. So "Stundensaldo" total / "Bilanz" mid-year is strongly negative, and only the running balance up to the current month is meaningful during the year (unclear whether this is intended).
- Older `Year.months` values may have had holidays baked in. `manage.py import_holidays` raises them back towards the weekday count so that holidays aren't subtracted twice (`workbench/management/commands/import_holidays.py:_adjust_year_months_smart`).

Code: `workbench/awt/reporting.py:annual_working_time`, `Months`, `holiday_days_by_month`, `holidays_of_year`, `working_time_by_week`, `vacation_planning_warnings`, `annual_working_time_warnings`. Helpers: `employment_percentages`, `full_time_equivalents_by_month`, `workbench/awt/utils.py:monthly_days`.

---

### Green hours (Grüne Stunden)

- Where: `/report/green-hours/` (`report_green_hours`), `GET /api/reports/green-hours/`. Feature: `CONTROLLING`.
- Answers: how much of each person's logged time in the period was within budget, beyond budget, maintenance or internal.

Project factor, computed over **all time** rather than the period:
`budget = Σ service_hours` of non-optional services whose offer is either absent or (not declined **and** not a budget retainer). Offers in preparation or offered count. `logged = Σ hours` of all logged hours on the project. `factor = budget / logged` if that is < 1, else 1. Projects without any qualifying service have a NULL budget, which means factor 1.

| Figure | Computation (hours in the period, per user) |
|---|---|
| Profitabel | `factor × hours` on Order projects |
| Überzogen | `(1 − factor) × hours` on Order projects |
| Wartung | hours on Maintenance projects |
| Intern | hours on Internal projects |
| Total | sum of the four |
| grün | `100 × (profitable + maintenance) / total` |
| external_percentage (API only) | `100 − 100 × internal / total` |

The users are the filter's users, or everyone who logged hours. The total row (key 0) sums the listed users, and rows with total 0 are dropped. Per-column percentages in the template are `x / total`.
`green_hours_by_month()` (same file, used by key data) gives the same figures per calendar month for all users with `p.type='order'`, `overdrawn = total − green − maintenance − internal`, and the percentage rounded to integers.
Code: `workbench/reporting/green_hours.py:green_hours`, `green_hours_by_month`.

---

### Hours per customer (Stunden pro Kundschaft)

- Where: `/report/hours-per-customer/` (`report_hours_per_customer`), `GET /api/reports/hours-per-customer/`. No feature, any logged-in user.
- Answers: who logged how many hours for which customer in the period.
- `Σ hours` grouped by `service.project.customer` and `rendered_by`, with `rendered_on` in the period and optional user filter. Internal projects count under their customer (usually the own organization). Customers are sorted by total, descending. The users columns are those with hours in the period. Totals: per customer, per user and overall.
- Code: `workbench/projects/reporting.py:hours_per_customer`.

---

### Hours per type (Stunden pro Typ)

- Where: `/report/hours-per-type/` (`report_hours_per_type`), `GET /api/reports/hours-per-type/`. Feature: `CONTROLLING`.
- Answers: how each person's hours split between external work and the internal types, compared with their target shares.

| Figure | Computation |
|---|---|
| Extern (Stunden) | hours on non-internal projects (Order + Maintenance) |
| per internal type (Stunden) | hours on internal projects grouped by `project.internal_type` |
| Richtwert, internal type | `InternalTypeUser.percentage` (the user's own value, or the type's default if empty), 0 if not assigned |
| Richtwert, Extern | `100 − Σ` of the user's internal Richtwerte |
| Erreicht | `100 × hours of the type / user's total hours` |
| Total / external / internal | per user and summed over users |

Highlights: external is green if Erreicht ≥ Richtwert and orange if it is more than 10 points below. Internal types are blue if above and orange if below half. The last internal type turns orange if it is more than 5 points above. The target percentages are not scaled by employment.
Code: `workbench/projects/reporting.py:hours_per_type`, `highlight_external`, `highlight_internal`.

---

### Logging statistics (Logbuch-Statistik)

- Where: `/report/logging/` (`report_logging`), `GET /api/reports/logging/`. Feature: `CONTROLLING`. All users, no team filter.
- Answers: how much, how promptly and with which breaks people log their time.

| Figure | Computation (logged hours with `rendered_on` in the period) |
|---|---|
| Anzahl / Summe / Durchschnitt | `COUNT(hours)`, `SUM(hours)`, `AVG(hours)` per user. The total average is `Σ sum / Σ count`. |
| Zeitpunkt der Erfassung | `AVG(created_at − (rendered_on + 12 h))` in hours: "Gleicher Tag" if < 8 h, "Nächster Tag" if < 30 h, otherwise "Spät" (shown in days) |
| Tage mit zuwenig Pausenzeit | days with logged hours where `hours ≥ 9 and breaks < 60 min`, `≥ 7 and < 30 min`, or `≥ 5.5 and < 15 min`. Breaks are `logbook_break` per day of `starts_at`. The figure is shown as "X of Y logged days", with a warning if the ratio is > 20%. |

Code: `workbench/logbook/reporting.py:logbook_stats`, `mean_logging_delay`, `classify_logging_delay`, `logged_hours_stats`, `insufficient_breaks`.

---

### Planning vs logbook (Planung vs Logbuch)

- Where: `/report/planning-vs-logbook/` (`report_planning_vs_logbook`), `GET /api/reports/planning-vs-logbook/`. No feature. Users come from the filter, or all users.
- Answers: per customer, how the logged hours compare with the planned hours in the period.

| Figure | Computation |
|---|---|
| Geplant | `PlannedWork` of the users (provisional included, any project state). `planned_hours / n_weeks / 5` per weekday, times the number of weekdays of that week inside the period, so partial first and last weeks are prorated. Grouped by `project.customer` and week. |
| Erfasst | `Σ hours` of the users' logged hours in the period by `project.customer` and week (internal projects included) |
| Differenz | `Erfasst − Geplant`. Red if `|diff| ≥ 16 h` or `≥ 20%` of `max(planned, logged)`, orange if `≥ 8 h` or `≥ 10%`, and orange if one side is zero. Rows are sorted by `|diff|`. |
| Zuteilung | `(logged_c / total_logged) / (planned_c / total_planned) × 100`, rounded to an integer. It is ∞ (None) if there are logged hours without planned hours, and 0 if nothing was logged. Red at ≥ 20 points from 100, orange at ≥ 10. Rows are faded if `planned_c < 0.25 × √total_planned`. |
| overall ratio (`logged_percentage`) | `total_logged / total_planned × 100`, rounded to an integer |

Code: `workbench/planning/reporting.py:planning_vs_logbook`, `_add_allocation`, `_diff_css_class`.

---

### Planning capacity (Verbleibende Kapazität pro Woche)

- Where: the user planning (`/users/<pk>/planning/`, `accounts_user_planning`) and the team planning (`/teams/<pk>/planning/`, active members) use the range today − 14 days … + 400 days, and the retrospective uses −180 … +14 days. API: `capacity` in `GET /api/planning/export/` when users or a team are given (active users only). XLSX export sheet "Capacity Analysis" ("Gesamtkapazität"). Label from `djangojs.po`. No feature.
- Answers: how many hours per week each person still has free after planned work, absences and holidays (negative means overbooked).

Per user and Monday `week`, the employment is the one with `date_from ≤ week < date_until`:

```
capacity = percentage × 5 × planning_hours_per_day / 100
         − Σ planned_hours / cardinality(weeks)              (all PlannedWork of the user with that week)
         − Σ absence.days × planning_hours_per_day / n_weeks (absences touching that week)
         − Σ holiday.fraction × planning_hours_per_day × percentage / 100
```

- `planning_hours_per_day` is a per-user field (default 8), separate from the WTM's `working_time_per_day`.
- Planned work counts whether it is provisional or not and whatever state the project has, distributed evenly over its weeks.
- Absences of **all** reasons count (including `other`). Their days are not scaled by the percentage (days as entered) and are distributed evenly over the calendar weeks from `date_trunc('week', starts_on)` (moved to the next week if the absence starts on a weekend) to `date_trunc('week', ends_on)` (`starts_on` if there is no end date).
- Holidays: those of the user's WTM in that week on weekdays (both kinds), scaled by the percentage.
- Weeks without an employment yield no capacity row (shown as 0). Partial weeks at the start or end of an employment aren't prorated, because only the Monday is checked.
- `total` = sum over users per week.

Worked example (made-up): 80%, `planning_hours_per_day` 8. In this week there is a public holiday on Monday (fraction 1), a vacation from Tuesday to Wednesday (`days = 2`, `ends_on` set), and planned work of 30 h spread over 3 weeks.
`0.8 × 5 × 8 = 32` − `30 / 3 = 10` − `2 × 8 = 16` − `1 × 8 × 0.8 = 6.4` = **−0.4 h** (slightly overbooked).

The display rows "absences" and "by week" in the same planning (`add_absences`, `add_public_holidays`) are computed in Python and differ slightly: absences spanning beyond the shown range put all their hours into the visible weeks.
Code: `workbench/planning/reporting.py:Planning.capacity`, `Planning.add_absences`, `Planning.add_public_holidays`, `user_planning`, `team_planning`. API: `workbench/planning/api.py:planning_export`.

## Deals

### Accepted deals (Gewonnene Geschäfte)

Web: `/report/accepted-deals/` (`report_accepted_deals`), feature DEALS; per-user modal `accepted-deals/deals/?user=ID`. API: `GET /api/deals/stats/` → `accepted` (DEALS; `users` filter = deal owners). `workbench/deals/reporting.py:accepted_deals`, `workbench/deals/api.py:deal_stats`
Answers: what value of deals was won in the period, per value type, month and person, vs. targets.

Deals: status ACCEPTED, `closed_on` in [Datum von, Datum bis] (default this week Mon–Sun). `Deal.value` = Σ of its `Value.value` rows (recomputed on save unless `skip_value_calculation`).

| Figure (DE) | Computation |
|---|---|
| Month × value type cells | Σ Value.value per value type, by month of `closed_on`. Columns: value types occurring in the deals plus all value types with a `weekly_target`. |
| Month "Total" | Σ of the month's values. |
| Total row per type | Σ over months; pie = sum vs. target. |
| Total row, overall cell | `stats.sum` = Σ of per-user contribution shares (see below), not Σ of values. |
| Ziel (n Wochen) | Per type: weekly_target × (days in period)/7; overall: Σ weekly_targets of the shown types × days/7. |
| Median-Alter | Days between `created_at` date and `closed_on`; one entry per Value row; upper median (`sorted[len//2]`). Overall median over all entries. |
| Per user: Wert | Σ over deals the user contributed to of Deal.value × contribution weight / Σ weights of that deal. |
| Per user: Anzahl | Number of deals the user contributed to. |
| Total row (users) | Anzahl = Σ of per-user counts; Wert = Σ of per-user values. |
| Deal list | Each deal's value; total row = `stats.sum`. |
| Modal per user | Deal, contact/customer, Projektvergabe (closing type + notice), Wert, Beitrag (the user's share). |

API additionally: declined `count`, `sum` (Σ Deal.value) and per closing type.

---

### Declined deals (Verlorene Geschäfte)

Web: `/report/declined-deals/` (`report_declined_deals`), DEALS. API: `/api/deals/stats/` → `declined`. `deals/reporting.py:declined_deals`
Answers: which deals were lost in the period and why.

Deals with status DECLINED and `closed_on` in the period (default this week), newest first. Columns: Geschäft, Kundschaft (contact with organization, else customer), Verlustgrund (closing_type + closing_notice), Wert (Deal.value). No totals in the web view; API: count, Σ value, count/Σ per closing type.

---

### Deal history (Geschichte der Geschäfte)

Web: `/report/deal-history/` (`report_deal_history`), DEALS. API: `GET /api/deals/history/`. `deals/reporting.py:deal_history`
Answers: what changed on deals in the period, and who changed it.

Audit log entries (`LoggedAction` for Deal) with `created_at` between Datum von 00:00 and Datum bis 23:59:59.999 (local time; default this week). Tracked fields: title, value, probability, decision_expected_on, status, closing_type, closing_notice (plus id). Team/user filter filters by the **user who made the change**; changes without a user are always included. No computed figures.

## Known inconsistencies

Found while writing this document (October 2026). The figures above
describe the current behaviour, including these. Remove an entry when it is
fixed or decided to be intended. Entries marked *(checked)* were confirmed
against the code or the database; the others were found by reading the code
and not checked a second time.

Profitability:

- The users' "Stunden" and "Ansatz" in squeeze include internal hours.
- Labor costs value "Ertrag" with `hours`, not `INVOICED_HOURS`; the per user
  modal shows no month in its title.
- `specs/squeeze-gross-margin.md` is outdated in §1.1 (third party costs are
  now the larger of invoiced and logged) and §1.3 (0.00 rates are weighted
  with `BASE_HOURLY_RATE`).

Financial overview and budgets:

- *(checked)* Key data deducts both logged third party costs not linked to
  an invoice and the third party costs entered on invoices
  (`key_data.py:third_party_costs_by_month`). Logged costs can't be linked to
  fixed amount invoices, so a cost entered on both counts twice; squeeze
  takes the larger of the two instead. Down payment invoices are left out
  here but not in squeeze and "Bank spielen".
- "davon geplant" and the projected gross margin ignore the cutoff date;
  offers and budget transfers are never limited by it either.
- "Rabatt" in the budget statistics counts offers which aren't declined,
  "verkauft" only accepted ones.
- Accruals stored for key data include internal projects, the cash data API
  leaves them out, so the same date can give two values. The first stored
  accruals record counts entirely as the change of its month.
- `accepted_offers_not_invoiced` in the cash data API includes budget
  retainer offers, "verkauft" in the budget statistics doesn't.
- The deals funnel of the key data API is always as of today.
- Totals of accepted deals add up per-person counts and shares: deals with
  several contributors count several times, deals without contributors are
  missing from the value.

Time and people:

- Capacity and the planning display only look at the employment on the
  Monday of a week (`date_from <= week < date_until`): an employment
  starting after Monday gives no capacity that week, one ending during the
  week gives the full week.
- Green hours count projects without budgeted services as profitable, and
  budgets include offers which aren't accepted yet.
- "Erwartet" in the user statistics ignores holidays and absences.
