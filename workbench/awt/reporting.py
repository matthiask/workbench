import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.utils.datastructures import OrderedSet

from workbench.awt.models import Absence, Employment, Year
from workbench.awt.utils import days_per_month, monthly_days
from workbench.logbook.models import LoggedHours
from workbench.tools.models import Z


class Months(dict):
    def __init__(self, *, year, users):
        self.year = year
        self.year_by_wtm = {
            year.working_time_model_id: year for year in Year.objects.filter(year=year)
        }
        self.users = users
        self.users_to_wtm = {user.id: user.working_time_model_id for user in users}

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            pass

        try:
            year = self.year_for_user(key)
        except KeyError:
            year = None

        self[key] = value = (
            {
                "year": year,
                "months": [dt.date(self.year, i, 1) for i in range(1, 13)],
                "target_days": year.months,
                "percentage": [Z for i in range(12)],
                "available_vacation_days": [Z for i in range(12)],
                "vacation_days": [Z for i in range(12)],
                "vacation_days_correction": [Z for i in range(12)],
                "other_absences": [Z for i in range(12)],
                "target": [Z for i in range(12)],
                "hours": [Z for i in range(12)],
                "employments": OrderedSet(),
            }
            if year
            else {"year": None}
        )
        return value

    def year_for_user(self, user_id):
        return self.year_by_wtm[self.users_to_wtm[user_id]]


def annual_working_time(year, *, users):
    absences = defaultdict(lambda: {"vacation_days": [], "other_absences": []})
    months = Months(year=year, users=users)
    vacation_days_credit = defaultdict(lambda: Z)
    dpm = days_per_month(year)

    for employment in Employment.objects.filter(user__in=users).order_by("-date_from"):
        percentage_factor = Decimal(employment.percentage) / 100
        available_vacation_days_per_month = (
            Decimal(employment.vacation_weeks) * 5 / 12 * percentage_factor
        )
        month_data = months[employment.user_id]
        if not month_data["year"]:
            continue

        for month, days in monthly_days(employment.date_from, employment.date_until):
            if month.year < year:
                continue
            elif month.year > year:
                break
            partial_month_factor = Decimal(days) / dpm[month.month - 1]
            month_data["target"][month.month - 1] += (
                month_data["year"].months[month.month - 1]
                * percentage_factor
                * partial_month_factor
                * month_data["year"].working_time_per_day
            )
            month_data["percentage"][month.month - 1] += (
                100 * percentage_factor * partial_month_factor
            )
            month_data["available_vacation_days"][month.month - 1] += (
                available_vacation_days_per_month * partial_month_factor
            )
            month_data["employments"].add(employment)

    for row in (
        LoggedHours.objects.order_by()
        .filter(rendered_by__in=users, rendered_on__year=year)
        .values("rendered_by")
        .annotate(month=ExtractMonth("rendered_on"))
        .values("rendered_by", "month")
        .annotate(Sum("hours"))
    ):
        month_data = months[row["rendered_by"]]
        if not month_data["year"]:
            continue

        month_data["hours"][row["month"] - 1] += row["hours__sum"]

    remaining = {
        user: sum(month_data["available_vacation_days"])
        for user, month_data in months.items()
    }
    for absence in Absence.objects.filter(
        user__in=users, starts_on__year=year
    ).order_by("starts_on"):
        month_data = months[absence.user_id]
        if not month_data["year"]:
            continue

        key = "vacation_days" if absence.is_vacation else "other_absences"
        month_data[key][absence.starts_on.month - 1] += absence.days
        absences[absence.user_id][key].append(absence)

        if absence.is_vacation:
            if absence.days > remaining[absence.user_id]:
                month_data["vacation_days_correction"][absence.starts_on.month - 1] += (
                    remaining[absence.user_id] - absence.days
                )
            remaining[absence.user_id] = max(
                0, remaining[absence.user_id] - absence.days
            )

    for user_id, vacation_days in remaining.items():
        if vacation_days > 0:
            vacation_days_credit[user_id] = vacation_days

    def absences_time(data):
        return [
            sum(
                (
                    data["vacation_days"][i],
                    data["vacation_days_correction"][i],
                    data["other_absences"][i],
                ),
                Z,
            )
            * data["year"].working_time_per_day
            for i in range(12)
        ]

    def working_time(data):
        at = absences_time(data)
        return [sum((data["hours"][i], at[i],), Z,) for i in range(12)]

    def monthly_sums(data):
        sums = [None] * 12
        wt = working_time(data)
        for i in range(12):
            sums[i] = wt[i] - data["target"][i]
        return sums

    statistics = []
    for user in users:
        month_data = months[user.id]
        if not month_data["year"]:
            continue

        sums = monthly_sums(month_data)
        at = absences_time(month_data)
        wt = working_time(month_data)
        statistics.append(
            {
                "user": user,
                "months": month_data,
                "absences": absences[user.id],
                "employments": month_data["employments"],
                "working_time": wt,
                "absences_time": at,
                "monthly_sums": sums,
                "running_sums": [sum(sums[:i], Z) for i in range(1, 13)],
                "totals": {
                    "target_days": sum(month_data["target_days"]),
                    "percentage": sum(month_data["percentage"]) / 12,
                    "available_vacation_days": sum(
                        month_data["available_vacation_days"]
                    ),
                    "vacation_days": sum(month_data["vacation_days"]),
                    "vacation_days_correction": sum(
                        month_data["vacation_days_correction"]
                    ),
                    "vacation_days_credit": vacation_days_credit[user.id],
                    "other_absences": sum(month_data["other_absences"]),
                    "target": sum(month_data["target"]),
                    "hours": sum(month_data["hours"]),
                    "absences_time": sum(at),
                    "working_time": sum(wt),
                    "running_sum": sum(sums),
                },
            }
        )

    return statistics
