# Verification rounds

Open findings of the verification rounds (see `AGENTS.md`), removed when
they're fixed or decided.

## Round 1 (2026-11-07)

### Questions (decisions)

- Cancelled invoices in key data include those cancelled while still in
  preparation (never sent). The form only warns that deleting may be
  cleaner (`discourage-cancellations`); should cancelling unsent invoices
  be impossible (delete them instead)?
- Logged costs which have been invoiced can still change their service and
  amounts behind the `part-of-invoice` warning (invoiced hours are locked
  since 82584a0a). Lock them too?
- Services can be created on closed projects (offers can't): needed for
  late costs and the few days of logging after closing?

### Decided, no change

- Reopening a project doesn't restore its discarded offers.
- Deleting or cancelling a services invoice doesn't undo `disable_logging`.
- Recurring invoices with `create_project` aren't closed automatically (see
  the journal note about closing projects automatically).
- Entries with `hours_for_invoicing=0` stay unarchived if their service has
  nothing else to invoice.
- CLI versions are plain numbers (`0.29.0`), no pre-releases.
- The history of sickness absences is only visible with
  `PERSONNEL_ADMINISTRATION` and pruned after three years.

### Data

- 2023-0161 has a flat rate (166) but six services of service groups at
  140/180 (since ae288a6c, saving the project applies the flat rate to
  them too).
