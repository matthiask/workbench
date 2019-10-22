import datetime as dt
from itertools import groupby

from django import forms
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.invoices.models import Invoice
from workbench.invoices.reporting import monthly_invoicing
from workbench.invoices.utils import next_valid_day
from workbench.projects.models import Project
from workbench.projects.reporting import overdrawn_projects, project_budget_statistics
from workbench.reporting import green_hours, key_data
from workbench.tools.formats import local_date_format
from workbench.tools.forms import DateInput
from workbench.tools.models import ONE, Z
from workbench.tools.validation import filter_form, monday
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
            .select_related("owned_by", "customer", "project")
        )

        return {
            "list": open_items,
            "total_excl_tax": sum((i.total_excl_tax for i in open_items), Z),
            "total": sum((i.total for i in open_items), Z),
        }


@filter_form(OpenItemsForm)
def open_items_list(request, form):
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
    last_month = next_valid_day(today.year, today.month + 1, 1) - dt.timedelta(days=1)
    date_range = [dt.date(last_month.year - 2, 1, 1), last_month]

    gross_margin_by_month = key_data.gross_margin_by_month(date_range)
    gross_margin_months = {
        row["month"]: row["gross_margin"] for row in gross_margin_by_month
    }

    gh = [
        row
        for row in green_hours.green_hours_by_month()
        if date_range[0] <= row["month"] <= date_range[1]
    ]

    def yearly_headline(gh):
        zero = {"green": Z, "red": Z, "maintenance": Z, "internal": Z, "total": Z}

        for key, months in groupby(gh, key=lambda row: row["month"].year):
            this = zero.copy()
            months = list(months)
            for month in months:
                this["green"] += month["green"]
                this["red"] += month["red"]
                this["maintenance"] += month["maintenance"]
                this["internal"] += month["internal"]
                this["total"] += month["total"]
            this["percentage"] = (
                100 * (this["green"] + this["maintenance"]) / this["total"]
            ).quantize(ONE)
            yield key, this, months

    return render(
        request,
        "reporting/key_data.html",
        {
            "date_range": date_range,
            "gross_margin_by_month": gross_margin_by_month,
            "invoiced_corrected": [
                (year, [gross_margin_months.get((year, i), Z) for i in range(1, 13)])
                for year in range(last_month.year - 2, last_month.year + 1)
            ],
            "green_hours": yearly_headline(gh),
            "hours_distribution": {
                "labels": [local_date_format(row["month"], "F Y") for row in gh],
                "datasets": [
                    {
                        "label": label,
                        "data": [100 * row[attribute] / row["total"] for row in gh],
                    }
                    for label, attribute in [
                        (_("profitable"), "green"),
                        (_("overdrawn"), "red"),
                        (_("maintenance"), "maintenance"),
                        (_("internal"), "internal"),
                    ]
                ],
            },
        },
    )


class HoursFilterForm(forms.Form):
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


@filter_form(HoursFilterForm)
def hours_filter_view(request, form, *, template_name, stats_fn):
    return render(
        request,
        template_name,
        {
            "form": form,
            "stats": stats_fn(
                [form.cleaned_data["date_from"], form.cleaned_data["date_until"]],
                users=form.cleaned_data["users"],
            ),
        },
    )


class ProjectBudgetStatisticsForm(forms.Form):
    owned_by = forms.TypedChoiceField(label="", coerce=int, required=False)
    s = forms.ChoiceField(
        choices=[
            ("all", _("All")),
            (
                _("status"),
                [("", _("Open")), ("closed", _("Closed during the last year"))],
            ),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "custom-select"}),
        label="",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(collapse_inactive=True)

    def queryset(self):
        data = self.cleaned_data
        if data.get("s") == "closed":
            queryset = Project.objects.closed().filter(
                closed_on__gte=timezone.now() - dt.timedelta(days=366)
            )
        elif data.get("s") == "all":
            queryset = Project.objects.all()
        else:
            queryset = Project.objects.open()
        queryset = queryset.exclude(type=Project.INTERNAL)
        if data.get("owned_by") == 0:
            queryset = queryset.filter(owned_by__is_active=False)
        elif data.get("owned_by"):
            queryset = queryset.filter(owned_by=data.get("owned_by"))
        return queryset.select_related("owned_by")


@filter_form(ProjectBudgetStatisticsForm)
def project_budget_statistics_view(request, form):
    return render(
        request,
        "reporting/project_budget_statistics.html",
        {
            "form": form,
            "projects": sorted(
                project_budget_statistics(form.queryset()),
                key=lambda project: project["delta"],
                reverse=True,
            ),
        },
    )


class DateRangeFilterForm(forms.Form):
    date_from = forms.DateField(
        label=_("date from"), required=False, widget=DateInput()
    )
    date_until = forms.DateField(
        label=_("date until"), required=False, widget=DateInput()
    )

    def __init__(self, data, *args, **kwargs):
        today = dt.date.today()
        data = data.copy()
        data.setdefault("date_from", dt.date(today.year, 1, 1).isoformat())
        data.setdefault("date_until", dt.date(today.year, 12, 31).isoformat())
        super().__init__(data, *args, **kwargs)


@filter_form(DateRangeFilterForm)
def green_hours_view(request, form):
    return render(
        request,
        "reporting/green_hours.html",
        {
            "form": form,
            "green_hours": green_hours.green_hours(
                [form.cleaned_data["date_from"], form.cleaned_data["date_until"]]
            ),
        },
    )
