import datetime as dt
import time
from collections import defaultdict

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.models import Absence, Year
from workbench.awt.reporting import active_users, annual_working_time


def annual_working_time_view(request):
    try:
        year = int(request.GET.get("year", dt.date.today().year))
    except Exception:
        return redirect(".")

    user = request.GET.get("user")
    users = None
    if user == "active" and request.user.features[FEATURES.CONTROLLING]:
        users = active_users(year)
    elif user and user != "active":
        users = User.objects.filter(id=user)
    if not users:
        users = [request.user]
    statistics = annual_working_time(year, users=users)
    for user in statistics["months"].users_without_wtm:
        messages.warning(
            request,
            _(
                "No annual working time defined for user %(user)s"
                " with working time model %(working_time_model)s."
            )
            % {"user": user, "working_time_model": user.working_time_model},
        )
    return render(
        request,
        "awt/year_detail.html",
        {
            "overall": statistics["overall"],
            "statistics": statistics["statistics"],
            "object": year,
            "year": year,
            "years": sorted(
                Year.objects.filter(year__lte=dt.date.today().year)
                .order_by()
                .values_list("year", flat=True)
                .distinct(),
                reverse=True,
            ),
            "view": {"meta": Year._meta},
        },
    )


def absence_calendar(request):
    absences = defaultdict(list)
    for absence in Absence.objects.calendar().select_related("user"):
        absences[absence.user].append(absence)

    absences = sorted(
        (
            (
                {"fullName": user.get_full_name(), "id": user.id},
                [
                    {
                        "id": absence.id,
                        "reason": absence.reason,
                        "reasonDisplay": absence.get_reason_display(),
                        "startsOn": time.mktime(absence.starts_on.timetuple()),
                        "endsOn": time.mktime(
                            (absence.ends_on or absence.starts_on).timetuple()
                        ),
                        "days": absence.days,
                        "description": absence.description,
                    }
                    for absence in user_absences
                ],
            )
            for user, user_absences in absences.items()
        ),
        key=lambda row: row[0]["fullName"],
    )

    return render(
        request,
        "awt/absence_calendar.html",
        {
            "absences_data": {
                "absencesByPerson": absences,
                "reasonList": Absence.REASON_CHOICES,
            }
        },
    )
