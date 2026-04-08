# Spec: Public Holidays and Company Holidays in AWT

## Goal

Integrate public holidays and company-specific holidays into the annual working
time (AWT) report, so that those days are explicitly called out rather than
silently showing up as an employee working-time deficit.

The feature must be **entirely optional**: if no holidays are entered the
behaviour is identical to today, so installations without holidays (e.g.
Blindflug) are not affected.

---

## 1. Move and extend the Holiday model

### From `planning.PublicHoliday` → `awt.Holiday`

The existing `planning.PublicHoliday` model already has the right shape.  It
moves to the AWT module and gets a `kind` field that distinguishes public
holidays (national/cantonal) from company holidays (company-specific days off).

```python
# workbench/awt/models.py

@model_urls
class Holiday(Model):
    class Kind(models.TextChoices):
        PUBLIC  = "public",  _("public holiday")
        COMPANY = "company", _("company holiday")

    date     = models.DateField(_("date"))
    name     = models.CharField(_("name"), max_length=200)
    fraction = models.DecimalField(
        _("fraction of day which is free"),
        default=1, max_digits=5, decimal_places=2,
    )
    kind = models.CharField(
        _("kind"), max_length=10, choices=Kind.choices, default=Kind.PUBLIC,
    )

    class Meta:
        ordering        = ["-date"]
        unique_together = [("date", "kind")]
        verbose_name        = _("holiday")
        verbose_name_plural = _("holidays")

    def __str__(self):
        return f"{self.name} ({local_date_format(self.date, fmt='l, j.n.')})"
```

**Changes vs. `planning.PublicHoliday`:**
- Renamed class and DB table (`awt_holiday`).
- `date` is no longer globally unique; uniqueness is now `(date, kind)` so a
  day can be both a public holiday and a company holiday (edge case, but
  possible).
- New `kind` field.

### Why the same model for both

Company holidays and public holidays have an identical data shape: a date, a
name, and optionally a partial-day fraction.  Using a single model with a `kind`
discriminator avoids duplication and allows the planning capacity calculations
to query both kinds in one pass.

---

## 2. Planning module updates

The `planning` module currently owns `PublicHoliday` and uses it in:

- `planning/reporting.py` — `Planning.add_public_holidays()` and the SQL inside
  `Planning.capacity()`.
- `planning/admin.py` — admin registration.
- `planning/urls.py` — `planning_publicholiday_detail` URL.
- The planning templates that link to the detail page.

**Required changes:**

1. Replace every `from workbench.planning.models import PublicHoliday` with
   `from workbench.awt.models import Holiday` and update references
   (`PublicHoliday` → `Holiday`).
2. The SQL queries that reference `planning_publicholiday` must be updated to
   `awt_holiday`.
3. The `planning_publicholiday_detail` URL name becomes `awt_holiday_detail`.
4. Remove `PublicHoliday` from `planning/models.py` and `planning/admin.py`
   once the migration is complete.

These are mechanical find-and-replace changes with no logic change.

---

## 3. Year model — "same sum of days"

The `Year` model stores target working days per month (e.g. `january = 23`).
Those 23 days currently include any public or company holidays; the Year record
was set up without them being separated out.

The goal is that the report can show:

```
January: 23 target days  =  21 normal days  +  2 public holidays
```

where `21 + 2 = 23` — the same sum as before.

**How it is implemented:** the holiday days per month are *derived* from
`Holiday` records at report time; no new fields are added to `Year`.  The
`Year.months` values are intentionally left unchanged — they still store the
total including holidays.

**How balance preservation works — the arithmetic:**

Let `H` = holiday days added in a month, `wpd` = working hours per day.

The migration command does two things atomically: insert `H` Holiday records
*and* increase `year.months[m]` by `H`.

```
Before  →  year.months[m] = 23,  H = 0
           target = 23 × 8h = 184h
           balance = logged − 184h

After   →  year.months[m] = 24,  H = 1
           effective_target = (24 − 1) × 8h = 23 × 8h = 184h   ← identical
           balance = logged − 184h                               ← unchanged ✓
```

The employee who was logging hours against a 23-day target continues to work
against exactly the same effective target.  The holiday days are now *visible*
in the report ("24 days in Year model − 1 public holiday = 23 effective working
days"), but the number everyone cares about — the balance — does not change.

For future years, admins enter the Year model values already including planned
holiday days, and configure the corresponding Holiday records.  The report
always shows the breakdown: `year.months[m] − H = effective working days`.

---

## 4. AWT reporting changes (`awt/reporting.py`)

### 4.1 Holiday days per month computation

Add a helper that returns holiday days per month for a given year, keyed by
`kind`:

```python
def holiday_days_by_month(year):
    """
    Returns {kind: [Decimal] * 12} for all Holiday records in `year`.
    Fraction is respected: a half-day holiday contributes 0.5.
    Weekends are excluded (holidays on Sat/Sun have no working-time effect).
    """
    result = {Holiday.Kind.PUBLIC: [Z1] * 12, Holiday.Kind.COMPANY: [Z1] * 12}
    for h in Holiday.objects.filter(date__year=year):
        if h.date.weekday() >= 5:   # skip weekends
            continue
        result[h.kind][h.date.month - 1] += h.fraction
    return result
```

### 4.2 Effective target

In `annual_working_time()`, after loading employment data, compute holiday days
and subtract them from the per-month target:

```python
holidays = holiday_days_by_month(year)
total_holiday_days = [
    holidays[Holiday.Kind.PUBLIC][i] + holidays[Holiday.Kind.COMPANY][i]
    for i in range(12)
]
# For each user's month_data, reduce target:
for i in range(12):
    reduction = total_holiday_days[i] * month_data["year"].working_time_per_day
    # Scale by partial-month / percentage factors already applied to target
    # ... (details: apply the same percentage/partial_month factor to reduction)
    month_data["target"][i] -= reduction
```

*(The exact scaling logic mirrors what is already done for the target itself.)*

Add `holiday_public` and `holiday_company` lists to `month_data` and to the
`totals` dict in `statistics`, so templates and PDFs can display them.

### 4.3 Overall aggregates

Add `holiday_public` and `holiday_company` keys to the `overall` dict in the
same way as other absence-type totals.

---

## 5. AWT report display

### Template (`awt/year_detail.html`)

Add two new rows to the per-user monthly table, between "target days" and
"vacation days":

- **Public holidays** — shown only if `holidays.PUBLIC` has any entries for the
  year
- **Company holidays** — shown only if `holidays.COMPANY` has any entries

Both rows show days per month and the annual total.  The "target days" row
label should clarify that it now represents *normal* working days (excluding
holidays) when holidays are present.

### PDF (`awt/pdf.py`)

Same new rows in `user_stats_pdf()`.  The cover summary section should also
include public/company holiday day totals.

---

## 6. Admin

Move `PublicHolidayAdmin` from `planning/admin.py` to `awt/admin.py`,
renamed to `HolidayAdmin`.  Register for `Holiday`.  Add `kind` and `fraction`
to `list_display` and `list_filter`.

---

## 7. Migration strategy

The DB table currently is `planning_publicholiday`.  The new table is
`awt_holiday`.

Suggested migration sequence:

1. **`awt` migration `0016_holiday`** — create `awt_holiday` table.
2. **`awt` data migration `0017_copy_public_holidays`** — copy all rows from
   `planning_publicholiday` into `awt_holiday` with `kind='public'`.
3. Update all code references (planning reporting, admin, URLs, templates) to
   use `awt.Holiday` and `awt_holiday_detail`.
4. **`planning` migration** — delete `planning_publicholiday` table (remove
   `PublicHoliday` model from `planning/models.py`).

Step 3 and 4 must land together in the same deploy to avoid a window where
planning reporting is broken.

---

## 8. Optionality / Blindflug

Every new section in the template and PDF is wrapped in a check:

```python
has_holidays = Holiday.objects.filter(date__year=year).exists()
```

Passed into template context.  When `False`:
- No "public holidays" or "company holidays" rows appear.
- No changes to the balance calculation (the reduction step is a no-op when
  `total_holiday_days` is all zeros).
- Blindflug sees no change at all.

---

## 9. Migration management command

Rather than a plain Django data migration, the holiday import and Year-model
adjustment should be performed by a management command that validates its own
work before committing anything.

### Command: `manage.py import_holidays`

Calculates holidays for a range of years using the existing
`workbench.planning.holidays` module (`get_public_holidays` and
`get_zurich_holidays`), then applies them inside a **single database
transaction**:

```
1. Compute "before" AWT state for all active users
2. Apply changes (insert Holiday rows, update Year month values)
3. Compute "after" AWT state for the same users
4. Compare before vs. after balances user-by-user
5a. If all balances match → commit
5b. If any discrepancy is found → raise CommandError → rollback
```

### Arguments

```
manage.py import_holidays [--dry-run]
```

The years to process are determined automatically from the `Year` model:
`Year.objects.values_list("year", flat=True).distinct()`.  No `--years`
argument is needed.

### Holiday calculation

For each year in the range the command collects holidays from two sources:

```python
from workbench.planning.holidays import get_public_holidays, get_zurich_holidays

def _collect_holidays(year):
    holidays = get_public_holidays(year)   # algorithmic (Easter etc.)
    zurich   = get_zurich_holidays(year)   # scrapes feiertagskalender.ch
    holidays.update(zurich)
    return holidays                        # {date: [name, fraction]}
```

**Verification step (before any DB writes):** after collecting, the command
asserts that both `"Sechseläuten"` and `"Knabenschiessen"` are present for
every year in the range.  If either is missing the command aborts immediately
with a clear error message — the scraper may have failed silently.

```python
REQUIRED_ZURICH = {"Sechseläuten", "Knabenschiessen"}

for year in years_to_check:
    found_names = {v[0] for v in _collect_holidays(year).values()}
    missing = REQUIRED_ZURICH - found_names
    if missing:
        raise CommandError(
            f"{year}: could not find {', '.join(sorted(missing))} — "
            "scraping feiertagskalender.ch may have failed."
        )
```

### Year model adjustments

The month deltas are derived automatically from the holiday dates: for each
holiday that falls on a weekday, add its `fraction` to the delta for that
month.  The delta is then applied to **every** `Year` record whose
`year` field matches (across all working-time models):

```python
from django.db.models import F
from workbench.awt.models import Year

def _adjust_year_months(year, month_deltas):
    # month_deltas: {1: Decimal("2"), 4: Decimal("0.5"), ...}  (1-indexed)
    year_obj = Year.objects.filter(year=year)
    for month_index, delta in month_deltas.items():
        field = Year.MONTHS[month_index - 1]          # e.g. "january"
        year_obj.update(**{field: F(field) + delta})
```

### Transaction skeleton

```python
from django.db import transaction
from workbench.awt.reporting import annual_working_time

TOLERANCE = Decimal("0.01")

def handle(self, *args, **options):
    years_to_check = _parse_years(options["years"])

    # collect + verify before opening the transaction
    all_holidays = {}
    for year in years_to_check:
        all_holidays[year] = _collect_holidays(year)   # aborts if data missing

    with transaction.atomic():
        # Step 1 — before state
        before = {}
        for year in years_to_check:
            awt = annual_working_time(year)
            before[year] = {
                row["user"].id: row["totals"]["balance"]
                for row in awt["statistics"]
            }

        # Step 2 — apply changes
        for year, holidays in all_holidays.items():
            _insert_holidays(year, holidays)     # Holiday.objects.bulk_create(...)
            month_deltas = _compute_month_deltas(holidays)
            _adjust_year_months(year, month_deltas)

        # Step 3 — after state
        after = {}
        for year in years_to_check:
            awt = annual_working_time(year)
            after[year] = {
                row["user"].id: row["totals"]["balance"]
                for row in awt["statistics"]
            }

        # Step 4 — compare
        discrepancies = []
        for year in years_to_check:
            for user_id, before_balance in before[year].items():
                after_balance = after[year].get(user_id)
                if after_balance is None:
                    continue
                if abs(after_balance - before_balance) > TOLERANCE:
                    discrepancies.append((year, user_id, before_balance, after_balance))

        # Step 5 — commit or abort
        if discrepancies:
            for year, user_id, b, a in discrepancies:
                self.stderr.write(f"Year {year} user {user_id}: {b}h → {a}h")
            raise CommandError("Balance discrepancies found — rolling back.")

        if options["dry_run"]:
            raise CommandError("Dry run — rolling back.")   # always rollback

        self.stdout.write("All balances preserved. Changes committed.")
```

### Tolerance

A small tolerance (`Decimal("0.01")`) accommodates rounding in the
existing target calculation.  Any difference larger than that is a real
discrepancy and aborts the migration.

### `--dry-run` flag

With `--dry-run`, the command runs all steps including the balance comparison
but always rolls back at the end, printing the before/after state without
touching the database.  Useful for previewing what would happen.

---

## 10. AWT summary Excel (`statistics.xlsx`)

When more than one user's PDF is downloaded, `awt/pdf.py` bundles all PDFs into
a ZIP and also generates `statistics.xlsx`.  The sheet is titled
**"running net work hours"** and currently has one row per user:

```
| Name | Jan | Feb | … | Dec | vacation days credit |
```

where the 12 monthly values are `running_sums` (cumulative net work hours).

### Required additions

Two extra columns are appended **after the 12 running-sum columns and before
the vacation-days-credit column**, but only when the year has at least one
Holiday record (`has_holidays` is true):

| Column | Value | Source |
|---|---|---|
| public holiday days | `data["totals"]["holiday_public"]` | sum of public holiday days for the year |
| company holiday days | `data["totals"]["holiday_company"]` | sum of company holiday days for the year |

The column headers are `_("public holiday days")` and
`_("company holiday days")`.

If `has_holidays` is false, the columns are omitted entirely, so the Excel
output is unchanged from today for installations without holidays.

### Code location

`annual_working_time_pdf()` in `awt/pdf.py`, inside the `zipfile` branch
(lines 38–53 approximately).  The `xlsx.table()` call needs:

```python
has_holidays = statistics.get("has_holidays", False)

header = (
    [""]
    + [date_format(day, "M") for day in data["months"]["months"]]
    + ([_("public holiday days"), _("company holiday days")] if has_holidays else [])
    + [_("vacation days credit")]
)
rows = [
    [d["user"].get_full_name()]
    + d["running_sums"]
    + (
        [d["totals"]["holiday_public"], d["totals"]["holiday_company"]]
        if has_holidays
        else []
    )
    + [d["totals"]["vacation_days_credit"]]
    for d in statistics["statistics"]
]
xlsx.table(header, rows)
```

`has_holidays` must be passed through from `annual_working_time()` in
`awt/reporting.py` (already computed for the template context, see section 8).

---

## 11. Decisions

All open questions have been resolved:

1. **Balance treatment**: Holidays **reduce target hours** (Option A).
   Effective target = `(year.months[m] − holiday_days) × working_time_per_day`.

2. **Per-user holiday allocation**: Holidays apply to all employed users.
   New employees are not onboarded mid-month in practice, so no
   employment-date filtering is required in the AWT report.

3. **Partial-day holidays**: `fraction < 1` contributes proportionally
   (e.g. `fraction=0.5` → 0.5 day reduction → 4 h for an 8 h/day year).

4. **Company holiday scope**: Company holidays apply to all employees.
   Per-team scoping is out of scope for v1.

5. **Planning URL change**: `planning_publicholiday_detail` → `awt_holiday_detail`.
   Redirects from the old URL path can be added if bookmarks need preserving.

6. **Year admin note**: Help text on the Year change form should read:
   "When public or company holidays are configured for this year, the
   corresponding month values must be **increased** by the number of holiday
   days (the management command does this automatically)."
