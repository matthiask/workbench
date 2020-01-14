import datetime as dt
import time
from collections import defaultdict

from django import forms
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import Team, User
from workbench.awt.models import Absence, Year
from workbench.awt.reporting import active_users, annual_working_time
from workbench.tools.forms import Form
from workbench.tools.validation import monday


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


class CalendarFilterForm(Form):
    team = forms.ModelChoiceField(
        Team.objects.all(), empty_label=_("Everyone"), label="", required=False
    )

    def queryset(self):
        data = self.cleaned_data
        queryset = Absence.objects.calendar().select_related("user")
        if data.get("team"):
            queryset = queryset.filter(user__teams=data.get("team"))
        return queryset


def absence_calendar(request):
    form = CalendarFilterForm(request.GET, request=request)
    form.is_valid()

    dates = {dt.date.today()}
    absences = defaultdict(list)
    for absence in form.queryset():
        absences[absence.user].append(absence)
        dates.add(absence.starts_on)
        dates.add(absence.ends_on)
    dates.discard(None)

    absences = sorted(
        (
            {
                "name": user.get_full_name(),
                "id": user.id,
                "absences": [
                    {
                        "id": absence.id,
                        "reason": absence.reason,
                        "reasonDisplay": absence.get_reason_display(),
                        "startsOn": time.mktime(absence.starts_on.timetuple()) * 1000,
                        "endsOn": time.mktime(
                            (absence.ends_on or absence.starts_on).timetuple()
                        )
                        * 1000,
                        "days": absence.days,
                        "description": absence.description,
                    }
                    for absence in user_absences
                ],
            }
            for user, user_absences in absences.items()
        ),
        key=lambda row: row["name"],
    )

    return render(
        request,
        "awt/absence_calendar.html",
        {
            "absences_data": {
                "absencesByPerson": absences,
                "reasonList": Absence.REASON_CHOICES,
                "timeBoundaries": {
                    "start": time.mktime(monday(min(dates)).timetuple()) * 1000,
                    "end": time.mktime(monday(max(dates)).timetuple()) * 1000,
                },
                "monday": time.mktime(monday().timetuple()),
            },
            "form": form,
        },
    )
