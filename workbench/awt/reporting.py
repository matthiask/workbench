import datetime as dt
from collections import defaultdict
from decimal import ROUND_UP, Decimal

from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from django.utils.datastructures import OrderedSet

from workbench.accounts.models import User
from workbench.awt.models import Absence, Employment, Year
from workbench.awt.utils import days_per_month, monthly_days
from workbench.logbook.models import LoggedHours
from workbench.tools.formats import Z1, Z2


class Months(dict):
    def __init__(self, *, year, users):
        self.year = year
        self.year_by_wtm = {
            year.working_time_model_id: year for year in Year.objects.filter(year=year)
        }
        self.users = users
        self.users_to_wtm = {user.id: user.working_time_model_id for user in users}
        self.users_with_wtm = [
            user for user in users if self.year_by_wtm.get(self.users_to_wtm[user.id])
        ]
        self.users_without_wtm = [
            user for user in users if user not in self.users_with_wtm
        ]

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            pass

        year = self.year_for_user(key)
        self[key] = value = {
            "year": year,
            "months": [dt.date(year.year, i, 1) for i in range(1, 13)],
            "target_days": year.months,
            "percentage": [Z1 for i in range(12)],
            "available_vacation_days": [Z1 for i in range(12)],
            "absence_vacation": [Z1 for i in range(12)],
            "absence_sickness": [Z1 for i in range(12)],
            "absence_paid": [Z1 for i in range(12)],
            "absence_correction": [Z1 for i in range(12)],
            "vacation_days_correction": [Z1 for i in range(12)],
            "target": [Z1 for i in range(12)],
            "hours": [Z1 for i in range(12)],
            "employments": OrderedSet(),
        }
        return value

    def year_for_user(self, user_id):
        return self.year_by_wtm[self.users_to_wtm[user_id]]


def active_users(year):
    return User.objects.filter(
        id__in=Employment.objects.filter(
            date_from__lte=dt.date(year, 12, 31),
            date_until__gte=dt.date(year, 1, 1),
        ).values("user")
    )


def full_time_equivalents_by_month():
    months = defaultdict(lambda: Z1)
    this_year = dt.date.today().year
    for employment in Employment.objects.all():
        percentage_factor = Decimal(employment.percentage) / 100
        for month, days in monthly_days(  # pragma: no branch
            employment.date_from, employment.date_until
        ):
            if month.year > this_year:
                break
            dpm = days_per_month(month.year)
            partial_month_factor = Decimal(days) / dpm[month.month - 1]
            months[month] += percentage_factor * partial_month_factor
    return months


def annual_working_time(year, *, users):
    absences = defaultdict(
        lambda: {
            "absence_vacation": [],
            "absence_sickness": [],
            "absence_paid": [],
            "absence_correction": [],
        }
    )
    months = Months(year=year, users=users)
    vacation_days_credit = defaultdict(lambda: Z1)
    dpm = days_per_month(year)

    for employment in Employment.objects.filter(
        user__in=months.users_with_wtm
    ).order_by("-date_from"):
        percentage_factor = Decimal(employment.percentage) / 100
        available_vacation_days_per_month = (
            Decimal(employment.vacation_weeks) * 5 / 12 * percentage_factor
        )
        month_data = months[employment.user_id]

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
        .filter(rendered_by__in=months.users_with_wtm, rendered_on__year=year)
        .values("rendered_by")
        .annotate(month=ExtractMonth("rendered_on"))
        .values("rendered_by", "month")
        .annotate(Sum("hours"))
    ):
        month_data = months[row["rendered_by"]]
        month_data["hours"][row["month"] - 1] += row["hours__sum"]

    remaining = defaultdict(
        lambda: Z1,
        {
            user: sum(month_data["available_vacation_days"])
            for user, month_data in months.items()
        },
    )
    for absence in Absence.objects.filter(
        user__in=months.users_with_wtm, starts_on__year=year, is_working_time=True
    ).order_by("starts_on"):
        month_data = months[absence.user_id]
        key = "absence_%s" % absence.reason
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
                    data["absence_vacation"][i],
                    data["absence_sickness"][i],
                    data["absence_paid"][i],
                    data["absence_correction"][i],
                    data["vacation_days_correction"][i],
                ),
                Z1,
            )
            * data["year"].working_time_per_day
            for i in range(12)
        ]

    def working_time(data):
        at = absences_time(data)
        return [sum((data["hours"][i], at[i]), Z1) for i in range(12)]

    def monthly_sums(data):
        sums = [None] * 12
        wt = working_time(data)
        for i in range(12):
            sums[i] = wt[i] - data["target"][i]
        return sums

    statistics = []
    for user in months.users_with_wtm:
        month_data = months[user.id]
        sums = monthly_sums(month_data)
        at = absences_time(month_data)
        wt = working_time(month_data)
        balance = (
            sum(sums)
            + month_data["year"].working_time_per_day * vacation_days_credit[user.id]
        )
        statistics.append(
            {
                "user": user,
                "months": month_data,
                "absences": absences[user.id],
                "employments": month_data["employments"],
                "working_time": wt,
                "absences_time": at,
                "monthly_sums": sums,
                "running_sums": [sum(sums[:i], Z1) for i in range(1, 13)],
                "totals": {
                    "target_days": sum(month_data["target_days"]),
                    "percentage": sum(month_data["percentage"]) / 12,
                    "available_vacation_days": sum(
                        month_data["available_vacation_days"]
                    ),
                    "absence_vacation": sum(month_data["absence_vacation"]),
                    "vacation_days_correction": sum(
                        month_data["vacation_days_correction"]
                    ),
                    "vacation_days_credit": vacation_days_credit[user.id].quantize(
                        Z2, rounding=ROUND_UP
                    ),
                    "balance": balance,
                    "balance_days": (
                        balance / month_data["year"].working_time_per_day
                    ).quantize(Z2, rounding=ROUND_UP),
                    "absence_sickness": sum(month_data["absence_sickness"]),
                    "absence_paid": sum(month_data["absence_paid"]),
                    "absence_correction": sum(month_data["absence_correction"]),
                    "target": sum(month_data["target"]),
                    "hours": sum(month_data["hours"]),
                    "absences_time": sum(at),
                    "working_time": sum(wt),
                    "running_sum": sum(sums).quantize(Z1),
                },
            }
        )

    overall = {
        key: sum((s["totals"][key] for s in statistics), Z1)
        for key in [
            "percentage",
            "available_vacation_days",
            "absence_vacation",
            "vacation_days_correction",
            "vacation_days_credit",
            "absence_sickness",
            "absence_paid",
            "absence_correction",
            "hours",
            "running_sum",
            "balance",
        ]
    }
    overall["absence_vacation"] -= overall["vacation_days_correction"]

    return {"months": months, "overall": overall, "statistics": statistics}
