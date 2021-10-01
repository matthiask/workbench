import datetime as dt

from django.conf import settings

from authlib.email import render_to_mail

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.reporting import annual_working_time_warnings
from workbench.tools.validation import logbook_lock


def is_previous_month_locked_starting_today():
    day = dt.date.today()
    if day != logbook_lock():
        return False
    if day == logbook_lock() and day.month == 1 and day.day != 1:
        return False
    if day.day > 7:
        return False
    return True


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
            cc=["workbench@feinheit.ch"],
        ).send()

    for user, running_sum in stats["warnings"]:
        if user in warning_individual:
            render_to_mail(
                "awt/individual_awt_warning_mail",
                {
                    "user": user,
                    "running_sum": running_sum,
                    "month": stats["month"],
                    "WORKBENCH": settings.WORKBENCH,
                },
                to=[user.email],
                cc=["workbench@feinheit.ch"],
            ).send()
