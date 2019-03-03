from datetime import date

from django.shortcuts import redirect, render

from . import invoicing_statistics, project_statistics


def monthly_invoicing(request):
    year = None
    if "year" in request.GET:
        try:
            year = int(request.GET["year"])
        except Exception:
            return redirect(".")
    if not year:
        year = date.today().year

    return render(
        request,
        "reporting/monthly_invoicing.html",
        {
            "year": year,
            "monthly_invoicing": invoicing_statistics.monthly_invoicing(year),
        },
    )


def overdrawn_projects(request):
    return render(
        request,
        "reporting/overdrawn_projects.html",
        {"overdrawn_projects": project_statistics.overdrawn_projects()},
    )
