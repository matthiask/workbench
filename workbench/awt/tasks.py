import datetime as dt
from decimal import Decimal

from authlib.email import render_to_mail
from django.conf import settings

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.holidays import (
    get_public_holidays,
    get_zurich_holidays,
    weekdays_per_month,
)
from workbench.awt.models import Holiday, WorkingTimeModel, Year
from workbench.awt.reporting import annual_working_time_warnings
from workbench.tools.validation import logbook_lock


def create_holidays():
    today = dt.date.today()
    for wtm in WorkingTimeModel.objects.all():
        prev_year = (
            Year.objects.filter(working_time_model=wtm).order_by("-year").first()
        )
        working_time_per_day = (
            prev_year.working_time_per_day if prev_year else Decimal(0)
        )

        for year in range(today.year, today.year + 3):
            weekdays = weekdays_per_month(year)
            Year.objects.get_or_create(
                year=year,
                working_time_model=wtm,
                defaults={
                    "working_time_per_day": working_time_per_day,
                    **{month: weekdays[i] for i, month in enumerate(Year.MONTHS)},
                },
            )

            days = get_public_holidays(year)
            days.update(get_zurich_holidays(year))
            Holiday.objects.bulk_create(
                [
                    Holiday(
                        date=date,
                        name=name,
                        fraction=fraction,
                        working_time_model=wtm,
                    )
                    for date, (name, fraction) in days.items()
                ],
                ignore_conflicts=True,
            )


def is_previous_month_locked_starting_today():
    day = dt.date.today()
    if day != logbook_lock():
        return False
    if day == logbook_lock() and day.month == 1 and day.day != 1:
        return False
    return not day.day > 7


def annual_working_time_warnings_mails():
    if not is_previous_month_locked_starting_today():
        return

    stats = annual_working_time_warnings()
    if not stats["warnings"]:
        return

    active_users = User.objects.active()

    warning_all = [
        user for user in active_users if user.features[FEATURES.AWT_WARNING_ALL]
    ]
    warning_individual = [
        user for user in active_users if user.features[FEATURES.AWT_WARNING_INDIVIDUAL]
    ]

    if warning_all:
        render_to_mail(
            "awt/awt_warning_mail",
            {"stats": stats, "WORKBENCH": settings.WORKBENCH},
            to=[user.email for user in warning_all],
            reply_to=[user.email for user in warning_all],
        ).send()

    for row in stats["warnings"]:
        if row["user"] in warning_individual:
            render_to_mail(
                "awt/individual_awt_warning_mail",
                row
                | {
                    "month": stats["month"],
                    "WORKBENCH": settings.WORKBENCH,
                },
                to=[row["user"].email],
                reply_to=[user.email for user in warning_all],
            ).send()
