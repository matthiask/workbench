---
name: workbench-deals
description: Keep the Workbench sales pipeline up to date with the `wb` CLI. Use when the user wants to review, update, clean up, close, win or lose deals, update probabilities or expected decision dates, or asks about the state of the pipeline or of a deal in Workbench.
---

# Keeping the Workbench sales pipeline up to date

The `wb` CLI talks to Workbench (see `wb --help`); deals require the deals
feature. If `wb` isn't installed or configured, tell the user to run
`uv tool install "git+https://github.com/matthiask/workbench#subdirectory=cli"`
and `wb login URL --write`. Only looking at deals works with `--read` too; if
`wb` answers that the token only allows reading, ask the user to log in with
`--write` instead of working around it.

## 1. Look at the pipeline

    wb deals search                          # Open deals, earliest decision first
    wb deals search --owned-by <short name>
    wb deals search --period this-month      # Decision expected (or closed) this month
    wb deals show <deal_id>
    wb notes search --deal <deal_id>         # What happened so far

Point out what looks stale:

- Open deals whose expected decision is in the past.
- High probability deals without an expected decision date.
- Deals without notes for a long time, deals whose values are missing.

Summarize per owner and ask the user what they know about each deal. Don't
guess outcomes, probabilities or dates; the user or the deal's owner knows.

## 2. Update deals

Change only what the user told you, one command per deal, first with
`--dry-run`:

    wb deals update <deal_id> --probability high --decision-expected-on 2026-12-15 --dry-run
    wb deals update <deal_id> --value Design=6000 --value Hosting= --dry-run

- `--value TYPE=AMOUNT` sets the value of a value type, `TYPE=` removes it.
  Unknown value types are rejected with a list of the choices.
- High probability requires an expected decision date.
- Add what you learned as a note so others see it:
  `wb notes create --deal <deal_id> --title "<title>" --description "<text>"`.
  The deal's owner is notified by email, mention that to the user.

## 3. Close deals

Closing works like in Workbench: accepting or declining a deal also accepts
or declines its related offers which haven't been accepted yet.

    wb deals close <deal_id> accepted --closing-type "<award of contract>" --dry-run
    wb deals close <deal_id> declined --closing-type "<reason>" --notice "<why>" --dry-run
    wb deals reopen <deal_id>

- Unknown closing types are rejected with a list of the choices; ask the user
  which one applies, especially the reason for losing.
- `--offer <offer_id>` (repeatable) picks the offers to accept or decline,
  `--keep-offers` leaves them alone. Show the user which offers would change.
- Declining offers with planned work needs `--delete-planned-work` or
  `--keep-planned-work`; ask the user.

## Rules

- Run every change with `--dry-run` first, show the user what changes and
  only run it without `--dry-run` after their explicit approval.
- Never close, decline or reopen deals on your own, and never invent values,
  probabilities, dates or reasons.
- `wb deals stats --period last-month` and `wb deals history --period
  this-week` show what was won, lost and changed, e.g. for a weekly review.
