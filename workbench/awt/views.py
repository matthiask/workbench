import datetime as dt
import time
from collections import defaultdict

from django.contrib import messages
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.awt.forms import CalendarFilterForm
from workbench.awt.models import Absence, Year
from workbench.awt.pdf import annual_working_time_pdf
from workbench.awt.reporting import active_users, annual_working_time
from workbench.tools.validation import filter_form, monday


def annual_working_time_view(request):
    this_year = dt.date.today().year
    try:
        year = int(request.GET.get("year", this_year))
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

    if request.GET.get("export") == "pdf":
        return annual_working_time_pdf(statistics)

    return render(
        request,
        "awt/year_detail.html",
        {
            "overall": statistics["overall"],
            "statistics": statistics["statistics"],
            "object": year,
            "year": year,
            "years": sorted(
                Year.objects.filter(year__lte=this_year + 1)
                .order_by()
                .values_list("year", flat=True)
                .distinct(),
                reverse=True,
            ),
            "view": {"meta": Year._meta},
            "is_last_year": year == this_year - 1,
            "this_year": this_year,
        },
    )


@filter_form(CalendarFilterForm)
def absence_calendar(request, form):
    users = form.users()

    absences = defaultdict(list)
    cutoff = form.cutoff()
    queryset = Absence.objects.annotate(
        _ends_on=Coalesce("ends_on", "starts_on")
    ).filter(
        starts_on__lte=cutoff + dt.timedelta(days=366),
        _ends_on__gte=cutoff,
        user__in=users,
    )

    dates = set()
    if not form.cleaned_data.get("year"):
        dates.add(dt.date.today())
    for absence in queryset:
        absences[absence.user_id].append(absence)
        dates.add(max(absence.starts_on, cutoff))
        dates.add(absence._ends_on)

    if not dates:
        messages.warning(request, _("Filter invalid, no absences available."))
        return HttpResponseRedirect(".")

    absences = [
        {
            "name": user.get_full_name(),
            "id": user.id,
            "absences": [
                {
                    "id": absence.id,
                    "reason": absence.reason,
                    "reasonDisplay": absence.get_reason_display(),
                    "startsOn": time.mktime(max(absence.starts_on, cutoff).timetuple())
                    * 1000,
                    "endsOn": time.mktime(
                        (absence.ends_on or absence.starts_on).timetuple()
                    )
                    * 1000,
                    "days": absence.days,
                    "description": absence.description,
                }
                for absence in absences[user.id]
            ],
        }
        for user in users
    ]

    return render(
        request,
        "awt/absence_calendar.html",
        {
            "absences_data": {
                "absencesByPerson": absences,
                "reasonList": Absence.REASON_CHOICES,
                "timeBoundaries": {
                    "start": time.mktime(monday(min(dates)).timetuple()) * 1000,
                    "end": time.mktime(max(dates).timetuple()) * 1000,
                },
                "monday": time.mktime(monday().timetuple()),
            },
            "form": form,
        },
    )
