import datetime as dt

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.circles.reporting import logged_hours_by_circle
from workbench.invoices.models import Invoice
from workbench.invoices.reporting import monthly_invoicing
from workbench.projects.models import Project
from workbench.projects.reporting import (
    hours_per_customer,
    overdrawn_projects,
    project_budget_statistics,
)
from workbench.reporting import key_data
from workbench.tools.forms import DateInput, Form
from workbench.tools.models import Z
from workbench.tools.validation import monday
from workbench.tools.xlsx import WorkbenchXLSXDocument


def monthly_invoicing_view(request):
    year = None
    if "year" in request.GET:
        try:
            year = int(request.GET["year"])
        except Exception:
            return redirect(".")
    if not year:
        year = dt.date.today().year

    return render(
        request,
        "reporting/monthly_invoicing.html",
        {"year": year, "monthly_invoicing": monthly_invoicing(year)},
    )


def overdrawn_projects_view(request):
    return render(
        request,
        "reporting/overdrawn_projects.html",
        {"overdrawn_projects": overdrawn_projects()},
    )


class OpenItemsForm(forms.Form):
    cutoff_date = forms.DateField(
        label=_("cutoff date"), required=False, widget=DateInput()
    )

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("cutoff_date", dt.date.today().isoformat())
        super().__init__(data, *args, **kwargs)

    def open_items_list(self):
        open_items = (
            Invoice.objects.filter(
                ~Q(status__in=[Invoice.IN_PREPARATION]),
                Q(invoiced_on__lte=self.cleaned_data["cutoff_date"]),
                Q(closed_on__gt=self.cleaned_data["cutoff_date"])
                | Q(closed_on__isnull=True),
            )
            .order_by("invoiced_on", "pk")
            .select_related("owned_by", "project")
        )

        return {
            "list": open_items,
            "total_excl_tax": sum((i.total_excl_tax for i in open_items), Z),
            "total": sum((i.total for i in open_items), Z),
        }


def open_items_list(request):
    form = OpenItemsForm(request.GET)
    if not form.is_valid():
        messages.warning(request, _("Form was invalid."))
        return redirect(".")

    if request.GET.get("xlsx"):
        xlsx = WorkbenchXLSXDocument()
        xlsx.table_from_queryset(
            form.open_items_list()["list"].select_related(
                "customer", "contact__organization", "owned_by", "project__owned_by"
            )
        )
        return xlsx.to_response(
            "open-items-list-{}.xlsx".format(
                form.cleaned_data["cutoff_date"].isoformat()
            )
        )

    return render(
        request,
        "reporting/open_items_list.html",
        {"form": form, "open_items_list": form.open_items_list()},
    )


def key_data_view(request):
    today = dt.date.today()
    last_month = today - dt.timedelta(days=today.day + 1)
    date_range = [dt.date(last_month.year - 2, 1, 1), last_month]

    green_hours = sorted(key_data.green_hours(date_range).items())

    return render(
        request,
        "reporting/key_data.html",
        {
            "date_range": date_range,
            "invoiced_corrected": [
                (year, [month_data[i] for i in range(1, 13)])
                for year, month_data in sorted(
                    key_data.invoiced_corrected(date_range).items()
                )
            ],
            "green_hours": [
                (year, [month_data["months"][i] for i in range(1, 13)])
                for year, month_data in green_hours
            ],
            "hours_distribution": {
                "labels": [
                    year
                    if year < last_month.year
                    else ("%s (%s)" % (year, _("projection")))
                    for year, month_data in (green_hours)
                ],
                "datasets": [
                    {
                        "label": label,
                        "data": [
                            100
                            * getattr(month_data["year"], attribute)
                            / month_data["year"].total
                            for year, month_data in green_hours
                        ],
                    }
                    for label, attribute in [
                        (_("profitable"), "profitable"),
                        (_("overdrawn"), "overdrawn"),
                        (_("maintenance"), "maintenance"),
                        (_("internal"), "internal"),
                    ]
                ],
            },
        },
    )


class LoggedHoursFilterForm(forms.Form):
    date_from = forms.DateField(
        label=_("date from"), required=False, widget=DateInput()
    )
    date_until = forms.DateField(
        label=_("date until"), required=False, widget=DateInput()
    )
    users = forms.ModelMultipleChoiceField(
        User.objects.all(), label=_("users"), required=False
    )

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("date_from", monday().isoformat())
        data.setdefault("date_until", (monday() + dt.timedelta(days=6)).isoformat())
        super().__init__(data, *args, **kwargs)
        self.fields["users"].choices = User.objects.choices(collapse_inactive=False)
        self.fields["users"].widget.attrs = {"size": 10}


def hours_per_customer_view(request):
    form = LoggedHoursFilterForm(request.GET)
    if not form.is_valid():
        messages.warning(request, _("Form was invalid."))
        return redirect(".")
    return render(
        request,
        "reporting/hours_per_customer.html",
        {
            "form": form,
            "stats": hours_per_customer(
                [form.cleaned_data["date_from"], form.cleaned_data["date_until"]],
                users=form.cleaned_data["users"],
            ),
        },
    )


def logged_hours_by_circle_view(request):
    form = LoggedHoursFilterForm(request.GET)
    if not form.is_valid():
        messages.warning(request, _("Form was invalid."))
        return redirect(".")
    return render(
        request,
        "reporting/logged_hours_by_circle.html",
        {
            "form": form,
            "stats": logged_hours_by_circle(
                [form.cleaned_data["date_from"], form.cleaned_data["date_until"]],
                users=form.cleaned_data["users"],
            ),
        },
    )


class ProjectBudgetStatisticsForm(Form):
    owned_by = forms.TypedChoiceField(label="", coerce=int, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(collapse_inactive=True)

    def queryset(self):
        data = self.cleaned_data
        queryset = Project.objects.open().exclude(type=Project.INTERNAL)
        if data.get("owned_by") == 0:
            queryset = queryset.filter(owned_by__is_active=False)
        elif data.get("owned_by"):
            queryset = queryset.filter(owned_by=data.get("owned_by"))
        return queryset.select_related("owned_by")


def project_budget_statistics_view(request):
    form = ProjectBudgetStatisticsForm(request.GET, request=request)
    if not form.is_valid():
        messages.warning(request, _("Form was invalid."))
        return redirect(".")

    return render(
        request,
        "reporting/project_budget_statistics.html",
        {
            "form": form,
            "projects": sorted(
                project_budget_statistics(form.queryset()),
                key=lambda project: project["invoiced"] - project["logbook"],
            ),
        },
    )
