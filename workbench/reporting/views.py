import datetime as dt
from itertools import groupby

from django import forms
from django.db.models import Q
from django.shortcuts import render
from django.utils.html import format_html, format_html_join
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import Team, User
from workbench.invoices.models import Invoice
from workbench.invoices.utils import next_valid_day
from workbench.logbook.models import LoggedCost
from workbench.projects.models import Project
from workbench.projects.reporting import overdrawn_projects
from workbench.reporting import (
    green_hours,
    key_data,
    labor_costs,
    project_budget_statistics,
)
from workbench.reporting.utils import date_ranges
from workbench.tools.formats import local_date_format
from workbench.tools.forms import DateInput, Form
from workbench.tools.models import ONE, Z
from workbench.tools.validation import filter_form, in_days, monday
from workbench.tools.xlsx import WorkbenchXLSXDocument


def overdrawn_projects_view(request):
    return render(
        request,
        "reporting/overdrawn_projects.html",
        {"overdrawn_projects": overdrawn_projects()},
    )


class OpenItemsForm(Form):
    cutoff_date = forms.DateField(label=capfirst(_("cutoff date")), widget=DateInput())

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


def key_data_details(fn):
    def view(request, year, month):
        year = int(year)
        month = int(month)
        date_range = [dt.date(year, month, 1)]
        date_range.append(next_valid_day(year, month + 1, 1) - dt.timedelta(days=1))
        return fn(request, date_range)

    return view


@key_data_details
def key_data_gross_profit(request, date_range):
    return render(
        request,
        "reporting/key_data_gross_profit.html",
        {
            "date_range": date_range,
            "invoices": Invoice.objects.valid()
            .filter(invoiced_on__range=date_range)
            .order_by("invoiced_on", "id")
            .select_related("project", "owned_by"),
        },
    )


@key_data_details
def key_data_third_party_costs(request, date_range):
    return render(
        request,
        "reporting/key_data_third_party_costs.html",
        {
            "date_range": date_range,
            "third_party_costs": LoggedCost.objects.filter(
                rendered_on__range=date_range,
                third_party_costs__isnull=False,
                invoice_service__isnull=True,
            )
            .order_by("rendered_on", "id")
            .select_related("service"),
            "invoices": Invoice.objects.valid()
            .filter(Q(invoiced_on__range=date_range), ~Q(third_party_costs=Z))
            .order_by("invoiced_on", "id")
            .select_related("project", "owned_by"),
        },
    )


def key_data_view(request):
    today = dt.date.today()
    this_months_end = next_valid_day(today.year, today.month + 1, 1) - dt.timedelta(
        days=1
    )
    date_range = [dt.date(this_months_end.year - 3, 1, 1), this_months_end]

    gross_margin_by_month = key_data.gross_margin_by_month(date_range)
    gross_margin_months = {
        row["month"]: row["gross_margin"] for row in gross_margin_by_month
    }

    gross_margin_by_years = {}
    for month in gross_margin_by_month:
        try:
            year = gross_margin_by_years[month["date"].year]
        except KeyError:
            gross_margin_by_years[month["date"].year] = year = {
                "year": month["date"].year,
                "gross_profit": Z,
                "third_party_costs": Z,
                "accruals": Z,
                "gross_margin": Z,
                "fte": [],
                "margin_per_fte": [],
                "months": [],
            }

        year["months"].append(month)
        year["gross_profit"] += month["gross_profit"]
        year["third_party_costs"] += month["third_party_costs"]
        year["accruals"] += month["accruals"]["delta"]
        year["gross_margin"] += month["gross_margin"]
        year["fte"].append(month["fte"])

    for year in gross_margin_by_years.values():
        year["fte"] = sum(year["fte"]) / len(year["fte"])
        year["margin_per_fte"] = (
            year["gross_margin"] / year["fte"] if year["fte"] else None
        )

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
            "gross_margin_by_years": [
                row[1] for row in sorted(gross_margin_by_years.items())
            ],
            "gross_margin_by_month": gross_margin_by_month,
            "invoiced_corrected": [
                (year, [gross_margin_months.get((year, i), Z) for i in range(1, 13)])
                for year in range(date_range[0].year, date_range[1].year + 1)
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
            "service_hours_in_open_orders": key_data.service_hours_in_open_orders(),
            "logged_hours_in_open_orders": key_data.logged_hours_in_open_orders(),
            "sent_invoices_total": key_data.sent_invoices_total(),
        },
    )


class ProjectBudgetStatisticsForm(Form):
    owned_by = forms.TypedChoiceField(label="", coerce=int, required=False)
    cutoff_date = forms.DateField(widget=DateInput, label="")
    closed_during_the_last_year = forms.BooleanField(
        label=_("Closed during the last year"), required=False
    )
    internal = forms.BooleanField(label=_("Internal"), required=False)

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        today = dt.date.today()
        data.setdefault("cutoff_date", today.isoformat())
        kwargs.setdefault("initial", {}).setdefault("cutoff_date", today)
        super().__init__(data, *args, **kwargs)
        self.fields["owned_by"].choices = User.objects.choices(
            collapse_inactive=True, myself=True
        )

    def queryset(self):
        data = self.cleaned_data
        if data.get("closed_during_the_last_year"):
            queryset = Project.objects.closed().filter(closed_on__gte=in_days(-366))
        else:
            queryset = Project.objects.open(on=self.cleaned_data.get("cutoff_date"))
        if data.get("internal"):
            queryset = queryset.filter(type=Project.INTERNAL)
        else:
            queryset = queryset.exclude(type=Project.INTERNAL)
        queryset = self.apply_owned_by(queryset)
        return queryset.select_related("owned_by")


@filter_form(ProjectBudgetStatisticsForm)
def project_budget_statistics_view(request, form):
    statistics = project_budget_statistics.project_budget_statistics(
        form.queryset(), cutoff_date=form.cleaned_data.get("cutoff_date")
    )

    if form.cleaned_data.get("closed_during_the_last_year"):
        statistics["statistics"] = sorted(
            statistics["statistics"], key=lambda s: s["project"].closed_on, reverse=True
        )

    if request.GET.get("xlsx") and statistics["statistics"]:
        xlsx = WorkbenchXLSXDocument()
        xlsx.project_budget_statistics(statistics)
        return xlsx.to_response("project-budget-statistics.xlsx")

    return render(
        request,
        "reporting/project_budget_statistics.html",
        {"form": form, "statistics": statistics},
    )


class DateRangeFilterForm(Form):
    date_from = forms.DateField(
        label=_("Date from"), required=False, widget=DateInput()
    )
    date_until = forms.DateField(
        label=_("Date until"), required=False, widget=DateInput()
    )
    team = forms.ModelChoiceField(
        Team.objects.all(),
        empty_label=_("Everyone"),
        label=capfirst(Team._meta.verbose_name),
        required=False,
    )

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("date_from", (monday() - dt.timedelta(days=7)).isoformat())
        data.setdefault("date_until", (monday() + dt.timedelta(days=6)).isoformat())
        super().__init__(data, *args, **kwargs)

        self.fields["date_from"].help_text = format_html(
            "{}: {}",
            _("Set predefined period"),
            format_html_join(
                ", ", '<a href="#" data-set-period="{}:{}">{}</a>', date_ranges()
            ),
        )

    def users(self):
        data = self.cleaned_data
        queryset = User.objects.all()
        if data.get("team"):
            queryset = queryset.filter(teams=data.get("team"))
        return queryset


@filter_form(DateRangeFilterForm)
def hours_filter_view(request, form, *, template_name, stats_fn):
    return render(
        request,
        template_name,
        {
            "form": form,
            "stats": stats_fn(
                [form.cleaned_data["date_from"], form.cleaned_data["date_until"]],
                users=form.users(),
            ),
        },
    )


def labor_costs_view(request):
    try:
        year = int(request.GET.get("year"))
    except Exception:
        year = dt.date.today().year

    date_range = [dt.date(year, 1, 1), dt.date(year, 12, 31)]

    if request.GET.get("project"):
        return render(
            request,
            "reporting/labor_costs_by_user.html",
            {
                "stats": labor_costs.labor_costs_by_user(
                    date_range, project=request.GET.get("project")
                ),
            },
        )
    elif request.GET.get("cost_center"):
        return render(
            request,
            "reporting/labor_costs_by_user.html",
            {
                "stats": labor_costs.labor_costs_by_user(
                    date_range, cost_center=request.GET.get("cost_center")
                ),
            },
        )
    elif request.GET.get("users"):
        return render(
            request,
            "reporting/labor_costs_by_user.html",
            {"stats": labor_costs.labor_costs_by_user(date_range)},
        )

    return render(
        request,
        "reporting/labor_costs.html",
        {"stats": labor_costs.labor_costs_by_cost_center(date_range)},
    )
