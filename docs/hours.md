# Logging hours

Hours are logged on a **service** of a project, best right after
finishing a task:

- You still know what you did, which helps when discussing the work with
  the customer later.
- Workbench fills in the time since your latest entry, you only check it.
- At the end of the day or week there's nothing left to catch up on.
- Breaks are logged in passing, Workbench knows when they started.

When that isn't possible (a call, a colleague at your desk, a meeting
away from the computer), set a [timestamp](#timestamps) and log the
hours later.

## Logging hours

<kbd>Ctrl-L</kbd> logs hours on the project you're looking at, else it
asks for the project first (<kbd>Ctrl-Shift-L</kbd> always asks). The
form fills in:

- **Hours**: the time since your latest activity of the day (logged
  hours, the end of a break, a timestamp), rounded up to the next tenth
  of an hour, if that's at most 12 hours.
- **Service**: the service you logged on last in this project.

A new project has no services yet: fill in "New service" in the same
form instead of choosing one. Use specific titles and descriptions, they
may end up on an offer or invoice.

**Hours for invoicing** stay empty in most cases: then the hours worked
are invoiced. Fill them in when a different number of hours should be
invoiced than the hours worked; they take precedence when creating
invoices, the hours worked still count for everything about time
(working time, planning, budgets in hours).

Hours are logged in the current week (from Monday, not before the first
of January); logging more than a day in advance asks whether that's
right, more than a week isn't possible. The hours of people allowed to log
late (where enabled) can also be logged in past weeks, the limits in
advance apply to them too. Projects stay open for logging for 14 days
after they have been closed.

The form warns about entries which look wrong: a duplicate of your
previous entry, a project closed recently, an entry already invoiced,
hours for invoicing lower or much higher than the hours worked, and,
where enabled, logging late and too few breaks. Check the entry and
choose "Ignore warnings" if it's correct.

On the [command line](cli.md), `wb hours create` and `wb costs create`
log hours and costs with the same checks; warnings stop with their code,
`--ignore-warning CODE` accepts them.

## Timestamps

A timestamp records when you stopped or started a task, with notes and
optionally the project. You turn them into logged hours or breaks later
on the [timestamps page](#the-timestamps-page).

- **Stop** ends a task: its notes describe the work you just finished.
- **Start** begins a task: its notes describe what you're starting. Use
  it in the morning and after breaks, so that the first task of the day
  or after the break has its beginning. A start followed by a stop is
  one task, their notes are joined.
- **Notes** become the description of the logged hours.
- **Project**: a project's ID or words from its title or customer, like
  the project search. A unique match among your pinned projects wins,
  otherwise the match among all open projects has to be unique. The
  project and its service are then filled in when logging the hours.
- **Time**: today's time if you forgot to press the button at the right
  moment.

The **controller**, a small window for timestamps, opens with
"Controller" on the timestamps page. It works without signing in, so you
can add it to your phone's home screen and set timestamps while away from
the computer. Its link contains your personal key: don't share it.

On the command line, `wb timestamps start` and `wb timestamps stop` do
the same (`wb timestamps --help`).

## The timestamps page

<kbd>Ctrl-T</kbd> (or "Timestamps" on the start page) lists your day as
slices: each with its times, its duration, the project and the notes.
Logged hours and breaks are part of the list, also those logged without
a timestamp.

- **+ Hours** opens the logbook form with the day, the duration, the
  notes and the project of the slice filled in.
- **+ Break** logs the slice as a break with its start and end.
- **Split** divides a slice into several parts (in tenths of an hour),
  e.g. when you worked on several projects without a timestamp in
  between. Log each part on its own.
- The cross deletes a timestamp you don't need.
- Gaps of more than two minutes between slices appear as
  "&lt;detected&gt;" and can be logged like the others.
- Logged slices link to their entry.

Hours logged on another day for this day come at the end, without times.
The arrows show earlier days. Workbench reminds you when many timestamps
of the current week haven't been logged yet.

## Breaks

<kbd>Ctrl-B</kbd> (or the plus button at the bottom left) logs a break:
it starts at your latest activity of the day and ends now, adjust both if
needed. <kbd>Ctrl-Shift-B</kbd> lists your breaks. Where enabled,
Workbench warns when you've worked more than 5.5, 7 or 9 hours a day
with less than 15, 30 or 60 minutes of breaks.

## Logging costs

<kbd>Ctrl-K</kbd> (or the plus button) logs costs on a service of a
project, like hours: expenses, licences, a print job. Internal costs go
on an internal project.

- **Third party costs**: what was paid to others, including tax.
- **Cost**: what the customer is invoiced. "100%" and "115%" copy the
  third party costs, the latter with a surcharge. Workbench warns when
  the third party costs are higher than the cost.
- **Paid from my own pocket** (where expense reports are enabled) marks
  expenses to be reimbursed; they need third party costs. Expenses in
  another currency keep their original currency and amount.
- "Payments" → "Expense reports" collects your expenses not reimbursed
  yet into a report. A closed report stays closed.

**Why including tax?** Third party costs are the total on the receipt,
including tax, because that's what was paid (and what's reimbursed for
expenses). The cost, like everything on an invoice, is an amount
excluding tax: the invoice adds the tax on top. That's no tax paid
twice: the company deducts the tax on the receipt as input tax, the
customer pays tax once, on the invoice. E.g. a receipt of 108.10
including 8.1% tax: third party costs 108.10, cost 108.10 ("100%"), the
invoice adds 8.76 tax.

Costs which have been invoiced keep their amounts.

## The timer

The timer (in the menu with your name) still exists, but timestamps are
the recommended way to keep track of your work.

Its activities stay where you put them. On a smaller screen the page
scrolls, and the − and + buttons below "+ Break" make the activities
smaller or larger in this browser.

To move several activities at once, drag a rectangle over them on an empty
spot (or Shift-click their titles) and drag one of them. A click on an
empty spot or Escape clears the selection.

"Arrange" lays out the selected activities (or all of them) in rows which
fit the window. "Undo" restores the previous positions until one of the
activities moves.
