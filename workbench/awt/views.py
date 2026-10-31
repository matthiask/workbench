import datetime as dt
import time
from collections import defaultdict

from django.contrib import messages
from django.db.models.functions import Coalesce
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from workbench.accounts.features import FEATURES, feature_required
from workbench.accounts.models import User
from workbench.awt.charts import (
    BALANCE_LIMIT,
    balance_chart,
    sparkline,
    vacation_meter,
    working_time_chart,
)
from workbench.awt.forms import CalendarFilterForm
from workbench.awt.models import HIDDEN_REASON, Absence, Year
from workbench.awt.pdf import annual_working_time_pdf
from workbench.awt.reporting import (
    active_users,
    annual_working_time,
    working_time_by_week,
)
from workbench.tools.validation import filter_form, monday


def annual_working_time_view(request):
    this_year = dt.date.today().year
    try:
        year = int(request.GET.get("year", this_year))
    except Exception:  # noqa: BLE001
        return redirect(".")

    user = request.GET.get("user")
    users = None
    overview_requested = False
    # The report contains sickness absences, which are health data
    if request.user.features[FEATURES.PERSONNEL_ADMINISTRATION]:
        if user == "active":
            overview_requested = True
            users = active_users(year)
        elif user:
            users = User.objects.filter(id=user)
    if not users:
        users = [request.user]
    statistics = annual_working_time(year, users=users)
    for misconfigured in statistics["months"].misconfigured_years:
        messages.error(
            request,
            _(
                "The annual working time %(year)s of the working time model"
                " %(working_time_model)s is not configured correctly:"
                " The working time per day is zero."
            )
            % {
                "year": misconfigured.year,
                "working_time_model": misconfigured.working_time_model,
            },
        )
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
        # The messages above say why there's nothing to export
        if not statistics["statistics"]:
            return redirect(f".?year={year}")
        return annual_working_time_pdf(statistics)

    return render(
        request,
        "awt/year_detail.html",
        {
            "overall": statistics["overall"],
            "overview": overview(statistics) if overview_requested else None,
            "statistics": []
            if overview_requested
            else [
                person_report(row, year=year, as_of=statistics["as_of"])
                for row in statistics["statistics"]
            ],
            "as_of": statistics["as_of"],
            "wtm_holiday_data": statistics["holidays_by_wtm"],
            "object": year,
            "year": year,
            "years": sorted(
                Year.objects
                .filter(year__lte=this_year + 1)
                .order_by()
                .values_list("year", flat=True)
                .distinct(),
                reverse=True,
            ),
            "view": {"meta": Year._meta},
            "is_last_year": year == this_year - 1,
            "this_year": this_year,
            "has_public_holidays": statistics["has_public_holidays"],
            "has_company_holidays": statistics["has_company_holidays"],
        },
    )


def overview(statistics):
    """One row per person, active people first"""
    as_of = statistics["as_of"]
    rows = [
        {
            "user": row["user"],
            "totals": row["totals"],
            "balance_beyond_limit": row["totals"]["balance_as_of"] is not None
            and abs(row["totals"]["balance_as_of"]) > BALANCE_LIMIT,
            "trend": sparkline(row["running_sums"][: as_of.month]) if as_of else None,
            "vacation_planning": row["vacation_planning"],
            "unconfirmed": any(
                absence.needs_confirmation
                for absences in row["absences"].values()
                for absence in absences
            ),
        }
        for row in statistics["statistics"]
    ]
    return {
        "active": [row for row in rows if row["user"].is_active],
        "inactive": [row for row in rows if not row["user"].is_active],
    }


def person_report(row, *, year, as_of):
    """Key figures, charts and the absences of one person's report"""
    totals = row["totals"]
    balance = totals["balance_as_of"]
    return row | {
        "balance_beyond_limit": balance is not None and abs(balance) > BALANCE_LIMIT,
        "balance_as_of_days": balance / row["months"]["year"].working_time_per_day
        if balance is not None
        else None,
        "balance_chart": balance_chart(
            working_time_by_week(year, user=row["user"]), as_of=as_of
        ),
        "working_time_chart": working_time_chart(row),
        "vacation_meter": vacation_meter(totals),
        "all_absences": sorted(
            [
                *(a for absences in row["absences"].values() for a in absences),
                *row["other_absences"],
            ],
            key=lambda absence: (absence.starts_on, absence.pk),
        ),
        "show_employments": len(row["months"]["employments"]) > 1
        or any(e.percentage != 100 for e in row["months"]["employments"]),
    }


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
                    "reason": absence.reason_for(request.user)[0],
                    "reasonDisplay": absence.reason_for(request.user)[1],
                    "startsOn": time.mktime(max(absence.starts_on, cutoff).timetuple())
                    * 1000,
                    "endsOn": time.mktime(
                        (absence.ends_on or absence.starts_on).timetuple()
                    )
                    * 1000,
                    "days": absence.days,
                    "description": absence.description_for(request.user),
                    "isConfirmed": not absence.needs_confirmation,
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
                "reasonList": Absence.REASON_CHOICES
                if request.user.features[FEATURES.PERSONNEL_ADMINISTRATION]
                else [*Absence.REASON_CHOICES, (HIDDEN_REASON, capfirst(_("absence")))],
                "timeBoundaries": {
                    "start": time.mktime(monday(min(dates)).timetuple()) * 1000,
                    "end": time.mktime(max(dates).timetuple()) * 1000,
                },
                "monday": time.mktime(monday().timetuple()),
            },
            "form": form,
        },
    )


@feature_required(FEATURES.PERSONNEL_ADMINISTRATION)
@require_POST
def confirm_absence(request, pk):
    absence = get_object_or_404(Absence, pk=pk)
    absence.confirm(request.user)
    absence.save()
    messages.success(request, _("The absence has been confirmed."))
    if request.is_ajax():
        return HttpResponse(status=202)  # Accepted, reloads the page
    return redirect(absence.urls["list"] + "?s=unconfirmed")
