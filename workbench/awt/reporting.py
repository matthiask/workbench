import datetime as dt
from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.utils.datastructures import OrderedSet

from workbench.awt.models import Absence, Employment
from workbench.awt.utils import days_per_month, monthly_days
from workbench.logbook.models import LoggedHours
from workbench.tools.models import Z


def annual_working_time(year, *, users):
    target_days = list(year.months)

    absences = defaultdict(lambda: {"vacation_days": [], "other_absences": []})
    months = defaultdict(
        lambda: {
            "months": [dt.date(year.year, i, 1) for i in range(1, 13)],
            "target_days": target_days,
            "percentage": [Z for i in range(12)],
            "available_vacation_days": [Z for i in range(12)],
            "vacation_days": [Z for i in range(12)],
            "vacation_days_correction": [Z for i in range(12)],
            "other_absences": [Z for i in range(12)],
            "target": [Z for i in range(12)],
            "hours": [Z for i in range(12)],
            "employments": OrderedSet(),
        }
    )
    dpm = days_per_month(year.year)

    for employment in Employment.objects.filter(user__in=users).order_by("-date_from"):
        percentage_factor = Decimal(employment.percentage) / 100
        available_vacation_days_per_month = (
            Decimal(employment.vacation_weeks) * 5 / 12 * percentage_factor
        )
        month_data = months[employment.user_id]
        for month, days in monthly_days(employment.date_from, employment.date_until):
            if month.year < year.year:
                continue
            elif month.year > year.year:
                break
            partial_month_factor = Decimal(days) / dpm[month.month - 1]
            month_data["target"][month.month - 1] -= (
                target_days[month.month - 1] * percentage_factor * partial_month_factor
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
        .filter(rendered_by__in=users, rendered_on__year=year.year)
        .values("rendered_by")
        .annotate(month=ExtractMonth("rendered_on"))
        .values("rendered_by", "month")
        .annotate(Sum("hours"))
    ):
        months[row["rendered_by"]]["hours"][row["month"] - 1] += row["hours__sum"]

    remaining = {
        user: sum(month_data["available_vacation_days"])
        for user, month_data in months.items()
    }
    for absence in Absence.objects.filter(
        user__in=users, starts_on__year=year.year
    ).order_by("starts_on"):
        key = "vacation_days" if absence.is_vacation else "other_absences"
        absences[absence.user_id][key].append(absence)
        month_data = months[absence.user_id]
        month_data[key][absence.starts_on.month - 1] += absence.days

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
            months[user_id]["vacation_days_correction"][11] = vacation_days

    def working_time(data):
        return [
            sum(
                (
                    data["hours"][i] / year.working_time_per_day,
                    data["vacation_days"][i],
                    data["vacation_days_correction"][i],
                    data["other_absences"][i],
                ),
                Z,
            )
            for i in range(12)
        ]

    def monthly_sums(data):
        sums = [None] * 12
        for i in range(12):
            sums[i] = data["hours"][i] + year.working_time_per_day * sum(
                (
                    data["vacation_days"][i],
                    data["vacation_days_correction"][i],
                    data["other_absences"][i],
                    data["target"][i],
                )
            )
        return sums

    statistics = []
    for user in users:
        user_data = months[user.id]
        sums = monthly_sums(user_data)
        wt = working_time(user_data)
        statistics.append(
            {
                "user": user,
                "months": user_data,
                "absences": absences[user.id],
                "employments": user_data["employments"],
                "working_time": wt,
                "monthly_sums": sums,
                "running_sums": [sum(sums[:i], Z) for i in range(1, 13)],
                "totals": {
                    "target_days": sum(user_data["target_days"]),
                    "percentage": sum(user_data["percentage"]) / 12,
                    "available_vacation_days": sum(
                        user_data["available_vacation_days"]
                    ),
                    "vacation_days": sum(user_data["vacation_days"]),
                    "vacation_days_correction": sum(
                        user_data["vacation_days_correction"]
                    ),
                    "other_absences": sum(user_data["other_absences"]),
                    "target": sum(user_data["target"]),
                    "hours": sum(user_data["hours"]),
                    "working_time": sum(wt),
                    "running_sum": sum(sums),
                },
            }
        )

    return statistics
