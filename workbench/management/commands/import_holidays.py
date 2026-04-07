import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.core.management import BaseCommand, CommandError

from workbench.awt.holidays import get_public_holidays, get_zurich_holidays
from workbench.awt.models import Holiday, WorkingTimeModel, Year


TOLERANCE = Decimal("0.01")
Z = Decimal(0)


def _weekdays_per_month(year):
    """Return a list of 12 weekday counts (Mon–Fri) for the given year."""
    result = []
    for month in range(1, 13):
        count = 0
        d = dt.date(year, month, 1)
        while d.month == month:
            if d.weekday() < 5:
                count += 1
            d += dt.timedelta(days=1)
        result.append(Decimal(count))
    return result


def _compute_month_deltas(holidays):
    deltas = defaultdict(lambda: Z)
    for date, (_name, fraction) in holidays.items():
        if date.weekday() >= 5:
            continue
        deltas[date.month] += fraction
    return dict(deltas)


def _insert_holidays(year, wtm, holidays):
    Holiday.objects.bulk_create(
        [
            Holiday(
                date=date,
                name=name,
                fraction=fraction,
                kind=Holiday.Kind.PUBLIC,
                working_time_model=wtm,
            )
            for date, (name, fraction) in holidays.items()
        ],
        ignore_conflicts=True,
    )


def _adjust_year_months_smart(year, wtm_id, month_deltas):
    """
    Bump Year.months per working-time-model record, but only by as much as
    each month is currently below the raw weekday count.  This handles two cases:

    - Holidays were already baked into Year.months (stored < weekdays):
      bump by min(delta, shortfall) to restore the raw weekday count so the
      new reporting's auto-subtraction produces the same effective target.

    - Fresh / blindflug setup where Year.months equals raw weekdays (shortfall=0):
      no bump, so the auto-subtraction is the only reduction.

    The operation is idempotent: a second run finds shortfall=0 and does nothing.
    """
    weekdays = _weekdays_per_month(year)
    for db_year in Year.objects.filter(year=year, working_time_model_id=wtm_id):
        stored = db_year.months
        updates = {}
        for month_index, delta in month_deltas.items():
            m = month_index - 1
            shortfall = weekdays[m] - stored[m]
            increment = min(delta, max(Z, shortfall))
            if increment > TOLERANCE:
                updates[Year.MONTHS[m]] = stored[m] + increment
        if updates:
            Year.objects.filter(pk=db_year.pk).update(**updates)


class Command(BaseCommand):
    help = "Import public holidays into awt.Holiday and adjust Year.months to match"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing anything",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            help="Compare stored Year.months values against computed weekday counts and exit",
        )

    def _check(self, years_to_check, all_holidays, wtms):
        month_names = Year.MONTHS
        for year in years_to_check:
            weekdays = _weekdays_per_month(year)
            for wtm in wtms:
                holiday_deltas = [Z] * 12
                for date, (_name, fraction) in all_holidays[year].items():
                    if date.weekday() < 5:
                        holiday_deltas[date.month - 1] += fraction
                expected = [weekdays[i] - holiday_deltas[i] for i in range(12)]

                db_years = list(Year.objects.filter(year=year, working_time_model=wtm))
                if not db_years:
                    continue

                for db_year in db_years:
                    stored = db_year.months
                    lines = []
                    for i, (s, w, e) in enumerate(zip(stored, weekdays, expected)):
                        if s - w != 0:
                            marker = "  *" if abs(s - e) > TOLERANCE else "   "
                            lines.append(
                                f"  {marker} {month_names[i]:12s}  stored={s:6}  weekdays={w:6}"
                                f"  holidays={holiday_deltas[i]:5}  expected={e:6}"
                                f"  Δ_from_expected={s - e:+7}"
                            )
                    if lines:
                        self.stdout.write(f"\n{year}  {db_year.working_time_model}")
                        for line in lines:
                            self.stdout.write(line)

    def handle(self, *args, **options):
        years_to_check = sorted(
            Year.objects.order_by().values_list("year", flat=True).distinct()
        )
        if not years_to_check:
            raise CommandError("No Year records found — nothing to do.")

        self.stdout.write(f"Collecting holidays for years: {years_to_check}")

        all_holidays = {}
        for year in years_to_check:
            holidays = get_public_holidays(year)
            holidays.update(get_zurich_holidays(year))
            all_holidays[year] = holidays
            self.stdout.write(f"  {year}: {len(holidays)} holidays")

        wtm_ids = set(
            Year.objects.filter(year__in=years_to_check).values_list(
                "working_time_model_id", flat=True
            )
        )
        wtms = list(WorkingTimeModel.objects.filter(id__in=wtm_ids))

        if options["check"]:
            self._check(years_to_check, all_holidays, wtms)
            return

        for year, holidays in all_holidays.items():
            month_deltas = _compute_month_deltas(holidays)
            for wtm in wtms:
                if options["dry_run"]:
                    weekdays = _weekdays_per_month(year)
                    for db_year in Year.objects.filter(
                        year=year, working_time_model=wtm
                    ):
                        stored = db_year.months
                        for month_index, delta in month_deltas.items():
                            m = month_index - 1
                            shortfall = weekdays[m] - stored[m]
                            increment = min(delta, max(Z, shortfall))
                            if increment > TOLERANCE:
                                self.stdout.write(
                                    f"  {year} {wtm} {Year.MONTHS[m]}: +{increment}"
                                )
                else:
                    _insert_holidays(year, wtm, holidays)
                    _adjust_year_months_smart(year, wtm.id, month_deltas)

        if not options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("Done."))
