# Planning

Planning shows who works on what in which weeks, next to absences and
the capacity left. It's about hours per week, not individual tasks.
Planning is available where your installation has enabled it.

## Where

- **Project**: "Planning" on the project page, with the project's
  milestones, its offers and the work planned for them.
- **Person**: "Planning" on your page (or "planned work" in the menu with
  your name) shows your weeks across all projects; "Retrospective" shows
  the past months.
- **Team** and **campaign** pages have their own planning.

## What's planned

- **Planned work**: a person, a title, the weeks (they need not be
  consecutive) and the **total** hours, spread evenly over the weeks.
  Optionally an offer and a milestone. **Provisional** work is planned
  but not definite, e.g. before an offer is accepted.
- **Milestones**: a date, optionally the start of their phase and a
  colour; work belonging to a milestone is drawn in its colour.
- **External work**: work done by the customer or others (e.g. feedback
  rounds, a print shop), without hours.

## Planning work

- Drag across weeks in the row of the project, an offer or a milestone,
  or click a single week: the form opens with those weeks.
- Drag a bar to move it, or its edges to make it longer or shorter. The
  total hours stay the same, so the hours per week change. Changes are
  saved right away.
- "Plan work" in the menu of an offer or a service on the project page
  fills in the title, notes and hours.
- In the form, select several weeks with Ctrl (Cmd on Macs).
- "Batch update" in the project's menu moves, reassigns or deletes
  several entries at once, or makes them definite. Across projects, e.g.
  to hand over the future work of someone who leaves, use
  `wb planning work batch`.

Workbench warns when work is planned after its milestone or belongs to
a declined offer, also in the batch update. Closed projects don't get
new planned work. Closing a project, declining an
offer or losing a deal asks whether to delete the planned work after the
current week; past work stays. Winning a deal doesn't change the
planning: make provisional work definite yourself. Whenever planned or
external work is deleted, or planned work is moved to another project,
milestones after the current week go with it when no work is left on
them.

## Capacity

The remaining capacity per week is your working days times your
"planning hours per day" (in your settings) and your percentage, minus
holidays, absences and **all** your planned work, provisional work
included. Negative capacity is shown in orange: someone is overbooked.
The start page lists provisional work of the next weeks so that it gets
decided.

## Importing a planning

"Import planning" in the project's menu creates a prompt for an AI tool
with the project, its offers, the people (by short name) and their
absences (without reasons). The prompt contains the project's
description and customer; only paste it into tools you may share that
with. Paste the tool's answer back: "Check" shows errors, warnings and a
preview, "Import" applies it.

## Mails

On Mondays, people involved get a mail with last week's changes to the
planned work and milestones of their projects and with the absences of
people in their projects. Nobody gets a mail listing only their own
changes. A project can turn these mails off for everybody.
