# Spec: Relaunching the annual working time report

## Goal

The annual working time report ("Jahresarbeitszeit",
`/report/annual-working-time/`) answers two questions:

1. Am I on track with my working time this year?
2. How many vacation days do I have left, and have I planned them?

Today the answers are hidden in the last rows of a table with up to 20 rows
and 14 columns per person. The relaunch puts the answers first and shows the
course of the year as charts. People with `PERSONNEL_ADMINISTRATION` get an
overview of everybody instead of a long stack of these tables.

The detailed table and the PDF stay as they are for now, so nobody loses the
view they are used to: the table moves into a collapsible section of the
report, the PDF export is unchanged.

The calculation (`annual_working_time()` in `workbench/awt/reporting.py`,
documented in `docs/metrics.md`) stays as it is; the new figures are derived
from it (section 4).

## 1. Today

`workbench/templates/awt/year_detail.html` renders per person:

- One table with a column per month and a total column. Rows: target days
  for full time employment, public holiday days, company holiday days,
  pensum, vacation days available, vacation days override, target time,
  vacation days taken, sickness days, paid leave, school attendance, working
  time correction, vacation days correction, countable absence hours, logged
  hours, working time, net work hours per month, running net work hours,
  vacation days credit and balance.
- A footer saying that monthly sums aren't exact because absences spanning
  months are split by calendar days.
- The employments, then lists of absences per reason in three columns, with
  a "vacation planning!" warning below the vacation list.

With "active users" (`?user=active`, requires `PERSONNEL_ADMINISTRATION`)
there are `wb-stats` tiles summing up everybody, followed by all of the above
for every person.

What makes it hard to read:

- **Calculation steps and results look the same.** Target days at 100%,
  holidays and pensum are only inputs to the target time; countable absence
  hours and working time are intermediate results. Only the running balance
  and the vacation days credit answer the questions above, and they come
  last.
- **Units are mixed** without saying so: days, percentages and hours
  alternate from row to row.
- **The future counts as missing work.** Target time is computed for all
  months of the year, logged hours only exist until today. During the year
  the monthly balances of the coming months are negative, the running
  balance drops month by month until December and the balance at the bottom
  is far below zero although the person is on track. One has to know to
  read the running balance of the last completed month instead.
- **Hours and vacation days are added up.** The balance at the bottom
  converts the unused vacation days into hours. Vacation days can't be
  converted though, they have to be taken.
- **Taken and planned vacation aren't distinguished.** "Vacation days taken"
  includes vacations in the future.
- **No comparison between people.** The overview for personnel
  administration is a stack of identical tables; finding the two people with
  a large overtime balance means scrolling through all of them.

## 2. The report of one person

Layout per the page conventions in `AGENTS.md` (`reporting/report.html`,
`wb-stats`, cards). The year and person selectors and the PDF export stay in
the header actions, a "New absence" action is added.

### 2.1 Key figures

`wb-stats` tiles at the top. Hours and vacation days are always separate
figures, never added up.

| Tile | Value | Note below the value |
|---|---|---|
| Balance | running balance at the end of the last completed month, in hours | "end of <month>"; the projection to today (4.2) if available |
| Vacation days left | entitlement − taken − planned | "x taken, y planned of z" |
| Sickness days | days | only the person and `PERSONNEL_ADMINISTRATION`, as today |

The balance at the end of the last month is what the monthly warning mails
use, and it doesn't depend on whether this week's hours are logged yet. For
past years it is the balance at the end of the year. In January of the
current year there is no completed month yet; the tile shows the end of the
previous year's balance in the note instead, or nothing.

Balances beyond ±40 h are highlighted. 40 h is the limit in the contracts
(independent of the pensum), but in practice it isn't applied strictly, so
the highlight is a quiet hint (`.wb-series-muted` or a subtle badge), not an
orange alarm.

### 2.2 Charts

Server-side SVG with `bar_chart()` from `workbench/tools/charts.py`, colors
from the `.wb-series-*` classes.

**Running balance**: a line of the running balance per week
(`working_time_by_week()` already computes `running_delta` up to the current
week) with bars of the weekly delta, and dashed lines at +40 h and −40 h.
Weeks of the current month are drawn lighter since their hours may not be
complete yet. Answers "on track?" at a glance and shows when the balance
built up. Weeks instead of months also avoid the "absences spanning months"
caveat for this chart.

**Working time per month**: stacked bars per month for logged hours and the
countable absence hours by reason (vacation, sickness, paid leave, school,
correction; sickness shown as "absence" to people who may not see reasons,
see `Absence.reason_for()`), plus a line for the target time. Future months
only show the target line and planned absences, lighter
(`.wb-series-muted`).

**Vacation**: a single horizontal meter (taken, planned, left) of the
entitlement, with the override noted below it if there is one. If more is
taken than available, the excess is shown in orange and explained ("x days
don't count as working time", the vacation days correction). Unused vacation
days are shown here only, not in the balance.

### 2.3 Absences and employments

- The vacation planning warning stays, next to the vacation meter.
- One list of all absences of the year, ordered by date, with reason (as
  visible to the viewer), period, days and confirmation status, instead of
  six separate lists in three columns. The "+" buttons per reason are
  replaced by the "New absence" action in the header.
- Employments stay as a small card, only shown if there is more than one
  employment in the year or the pensum isn't 100%.

### 2.4 Details

Today's monthly table, unchanged, in a collapsed `<details>` section
("Details") at the end of the page, including the footer note and the
holiday modals. It is the same view as in the PDF. Restructuring it (grouping
the rows, units in the row headers, dropping the combined balance row) can
follow later, together with the PDF.

## 3. The overview for personnel administration

`?user=active` doesn't render every person's report anymore but a table with
one row per person (`section.card.wb-table-card`, no zebra stripes):

| Person | Pensum | Balance | Trend | Vacation left | Planned | Sickness days | Warnings |
|---|---|---|---|---|---|---|---|

- Balance at the end of the last completed month in hours, highlighted like
  the tile in 2.1, sortable.
- Trend: a small sparkline of the running balance per month (a variant of
  `bar_chart()` without axes, or a minimal SVG polyline).
- Warnings: vacation planning (`vacation_planning_warnings()`), unconfirmed
  paid leave, balance beyond ±40 h.
- The person links to their report (`?user=<id>`).
- A totals row (`.wb-total-row`). Of today's tiles only those without a
  column stay: sickness days per full time equivalent, paid leave, school
  attendance, corrections. The combined "balance" tile goes away.

Inactive people (left during the year) are listed below the active ones,
muted, since their balance is final.

The PDF export of all active users (ZIP) is unchanged.

## 4. New figures

### 4.1 As of the end of the last month

Computed in `annual_working_time()` from what it already has, with `as_of`
being the end of the last completed month for the current year, the end of
the year for past years and nothing for future years:

- `balance_as_of`: `running_sums[as_of.month - 1]`.
- `vacation_days_taken` (vacation absences ending on or before today; a
  vacation spanning today is split by working days) and
  `vacation_days_planned` (the rest). Vacation counts as taken up to today,
  not up to the end of last month: a vacation last week is taken.
- `vacation_days_left`: available − taken − planned, may be negative
  (`vacation_days_credit` is the same clipped at zero and rounded up).

The API (`GET /api/reports/working-time/`) and `wb reports working-time`
get these fields so the CLI shows the same answers. Existing fields stay.

### 4.2 Projection to today (optional)

Where the balance would be today: `balance_as_of` + working time of the
current month so far − target time of the current month up to today
(prorated by working days like `working_time_by_week()`). The difficulty is
that hours of the last days are often not logged yet, so the projection
would be too low. Options:

- Only count the target up to the last day with logged hours, or up to the
  end of last week (people tend to log by the end of the week).
- Show it only as a note ("today about +12 h"), never as the main figure.

Proposal: up to the end of last week, as a note on the balance tile, and
leave it out entirely if it turns out to be noisy.

### 4.3 Splitting absences by working days (optional)

Absences spanning months are split by calendar days today, hence the footer
note. `working_time_by_week()` already spreads absences over weekdays.
Splitting the monthly figures the same way makes the note unnecessary and the
monthly and weekly figures agree. The annual totals don't change, the
monthly figures in the PDF would.

`docs/metrics.md` is updated in the same commits.

## 5. Steps

1. New figures (4.1) in `annual_working_time()`, tests, `docs/metrics.md`,
   API fields and `wb reports working-time` output.
2. Report of one person: key figures, the three charts, combined absence
   list, today's table in a collapsible section.
3. Overview for personnel administration.
4. Optional: projection to today (4.2), splitting absences by working days
   (4.3).

## 6. Later

- Restructure the detailed table and the PDF the same way (groups, units, no
  combined balance of hours and vacation days).
