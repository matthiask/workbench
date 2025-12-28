import datetime as dt
from collections import defaultdict
from decimal import Decimal
from functools import reduce
from itertools import groupby

from django import forms
from django.db.models import Q
from django.shortcuts import render
from django.utils.html import format_html, format_html_join
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from more_itertools import chunked

from workbench.accounts.models import Team, User
from workbench.accounts.reporting import (
    average_employment_duration,
    birthdays,
    work_anniversaries,
)
from workbench.invoices.models import Invoice
from workbench.invoices.utils import next_valid_day
from workbench.logbook.models import LoggedCost
from workbench.logbook.reporting import logbook_stats
from workbench.projects.models import Project
from workbench.reporting import (
    green_hours,
    key_data,
    labor_costs,
    project_budget_statistics,
    third_party_costs,
)
from workbench.reporting.utils import date_ranges
from workbench.tools.formats import Z0, Z2, local_date_format
from workbench.tools.forms import DateInput, Form
from workbench.tools.validation import filter_form, in_days, monday
from workbench.tools.xlsx import WorkbenchXLSXDocument


class OpenItemsForm(Form):
    cutoff_date = forms.DateField(label=capfirst(_("cutoff date")), widget=DateInput())

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("cutoff_date", dt.date.today().isoformat())
        super().__init__(data, *args, **kwargs)

    def open_items_list(self):
        open_items = (
            Invoice.objects
            .invoiced()
            .filter(
                Q(invoiced_on__lte=self.cleaned_data["cutoff_date"]),
                Q(closed_on__gt=self.cleaned_data["cutoff_date"])
                | Q(closed_on__isnull=True),
            )
            .order_by("invoiced_on", "pk")
            .select_related("owned_by", "customer", "project")
        )

        weeks = defaultdict(lambda: {"total_excl_tax": Z2, "total": Z2})
        for invoice in open_items:
            week = monday(invoice.due_on)
            weeks[week]["total_excl_tax"] += invoice.total_excl_tax
            weeks[week]["total"] += invoice.total

        return {
            "list": open_items,
            "weeks": sorted(weeks.items()),
            "total_excl_tax": sum((i.total_excl_tax for i in open_items), Z2),
            "total": sum((i.total for i in open_items), Z2),
        }


@filter_form(OpenItemsForm)
def open_items_list(request, form):
    if request.GET.get("export") == "xlsx":
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
            "invoices": Invoice.objects
            .invoiced()
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
            "third_party_costs": LoggedCost.objects
            .filter(
                rendered_on__range=date_range,
                third_party_costs__isnull=False,
                invoice_service__isnull=True,
            )
            .order_by("rendered_on", "id")
            .select_related("service"),
            "invoices": Invoice.objects
            .invoiced()
            .filter(~Q(type=Invoice.DOWN_PAYMENT))
            .filter(Q(invoiced_on__range=date_range), ~Q(third_party_costs=Z2))
            .order_by("invoiced_on", "id")
            .select_related("project", "owned_by"),
        },
    )


def projected_gross_margin(request):
    pi = key_data.projected_gross_margin()
    all_months = sorted(
        reduce(lambda a, b: a | b["monthly"].keys(), pi["projects"], set())
    )

    return render(
        request,
        "reporting/projected_gross_margin.html",
        {
            "projects": sorted(
                (
                    project
                    | {"monthly": [project["monthly"].get(m, Z2) for m in all_months]}
                    for project in pi["projects"]
                ),
                key=lambda project: project["monthly"],
                reverse=True,
            ),
            "months": [dt.date(m[0], m[1], 1) for m in all_months],
            "monthly_overall": [pi["monthly_overall"].get(m) for m in all_months],
        },
    )


def key_data_view(request):
    today = dt.date.today()
    date_range = [dt.date(today.year - 3, 1, 1), dt.date(today.year, 12, 31)]

    gross_margin_by_month = key_data.gross_margin_by_month(date_range)
    gross_margin_months = {
        row["month"]: row["gross_margin"] for row in gross_margin_by_month
    }

    projected_gross_margin = key_data.projected_gross_margin()

    gross_margin_by_years = defaultdict(
        lambda: {
            "year": month["date"].year,
            "gross_profit": Z2,
            "third_party_costs": Z2,
            "accruals": Z2,
            "gross_margin": Z2,
            "projected_gross_margin": Z2,
            "fte": [],
            "margin_per_fte": [],
            "months": [],
        }
    )

    for month in gross_margin_by_month:
        year = gross_margin_by_years[month["date"].year]
        year["months"].append(month)
        year["gross_profit"] += month["gross_profit"]
        year["third_party_costs"] += month["third_party_costs"]
        year["accruals"] += month["accruals"]["delta"]
        year["gross_margin"] += month["gross_margin"]
        year["projected_gross_margin"] += month["projected_gross_margin"] or Z2
        year["fte"].append(month["fte"])

    for year in gross_margin_by_years.values():
        year["fte"] = sum(year["fte"]) / len(year["fte"])
        year["margin_per_fte"] = (
            year["gross_margin"] / year["fte"] if year["fte"] else None
        )

    gmp_factor = Decimal("365.24") / Decimal((today - dt.date(today.year, 1, 1)).days)
    gm = gross_margin_by_years[today.year]
    gross_margin_projection = {
        "gross_profit": gm["gross_profit"] * gmp_factor,
        "gross_margin": gm["gross_margin"] * gmp_factor,
        "gross_margin_incl_projected": gm["gross_margin"] * gmp_factor
        + gm["projected_gross_margin"],
        "margin_per_fte": (
            gm["gross_margin"] * gmp_factor + gm["projected_gross_margin"]
        )
        / gm["fte"]
        if gm["fte"]
        else None,
    }

    gh = [
        row
        for row in green_hours.green_hours_by_month()
        if date_range[0] <= row["month"] <= date_range[1]
    ]

    def yearly_headline(gh):
        zero = {
            "profitable": Z2,
            "overdrawn": Z2,
            "maintenance": Z2,
            "internal": Z2,
            "total": Z2,
        }

        for key, months in groupby(gh, key=lambda row: row["month"].year):
            this = zero.copy()
            months = list(months)
            for month in months:
                this["profitable"] += month["profitable"]
                this["overdrawn"] += month["overdrawn"]
                this["maintenance"] += month["maintenance"]
                this["internal"] += month["internal"]
                this["total"] += month["total"]
            this["percentage"] = (
                100 * (this["profitable"] + this["maintenance"]) / this["total"]
            ).quantize(Z0)
            yield key, this, months

    gross_margin_by_years = [row[1] for row in sorted(gross_margin_by_years.items())]
    return render(
        request,
        "reporting/key_data.html",
        {
            "date_range": date_range,
            "gross_margin_by_years": gross_margin_by_years,
            "gross_margin_projection": gross_margin_projection,
            "gross_margin_by_month": gross_margin_by_month,
            "invoiced_corrected": [
                (year, [gross_margin_months.get((year, i), Z2) for i in range(1, 13)])
                for year in range(date_range[0].year, date_range[1].year + 1)
            ],
            "projected_gross_margin": [
                projected_gross_margin["monthly_overall"].get((today.year, i), Z2)
                for i in range(1, 13)
            ],
            "invoiced_corrected_per_fte": [
                (
                    year["year"],
                    [
                        sum(month["margin_per_fte"] or 0 for month in quarter)
                        for quarter in chunked(year["months"], 3)
                    ],
                )
                for year in gross_margin_by_years
            ],
            "green_hours": yearly_headline(gh),
            "hours_distribution": {
                "labels": [local_date_format(row["month"], fmt="F Y") for row in gh],
                "datasets": [
                    {
                        "label": label,
                        "data": [100 * row[attribute] / row["total"] for row in gh],
                    }
                    for label, attribute in [
                        (_("profitable"), "profitable"),
                        (_("maintenance"), "maintenance"),
                        (_("overdrawn"), "overdrawn"),
                        (_("internal"), "internal"),
                    ]
                ],
            },
            "service_hours_in_open_orders": key_data.service_hours_in_open_orders(),
            "logged_hours_in_open_orders": key_data.logged_hours_in_open_orders(),
            "sent_invoices_total": key_data.sent_invoices_total(),
            "due_invoices_total": key_data.due_invoices_total(),
            "open_offers_total": key_data.open_offers_total(),
            "average_employment_duration": average_employment_duration(),
        },
    )


class ProjectBudgetStatisticsForm(Form):
    owned_by = forms.TypedChoiceField(label="", coerce=int, required=False)
    cutoff_date = forms.DateField(widget=DateInput, label="")
    s = forms.ChoiceField(
        choices=[
            ("", _("All")),
            ("no-invoices", _("No invoices")),
            ("maintenance", _("Maintenance")),
            ("old-projects", _("Old projects (60 days inactivity)")),
            ("no-projected-gross-margin", _("No projected gross margin")),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )
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

        users = [(user.id, user) for user in User.objects.filter(is_active=True)]
        open_project_owners = set(
            Project.objects
            .open()
            .external()
            .order_by()
            .values_list("owned_by", flat=True)
            .distinct()
        )

        self.fields["owned_by"].choices = [
            ("", _("All users")),
            (-1, _("Show mine only")),
            (0, _("Inactive users")),
            (
                _("Open customer projects right now"),
                [choice for choice in users if choice[0] in open_project_owners],
            ),
            (
                _("Other active users"),
                [choice for choice in users if choice[0] not in open_project_owners],
            ),
        ]

    def queryset(self):
        data = self.cleaned_data
        if data.get("closed_during_the_last_year"):
            queryset = Project.objects.closed().filter(closed_on__gte=in_days(-366))
        else:
            queryset = Project.objects.open(on=self.cleaned_data.get("cutoff_date"))
        if data.get("s") == "no-invoices":
            queryset = queryset.orders().without_invoices()
        elif data.get("s") == "maintenance":
            queryset = queryset.filter(type=Project.MAINTENANCE)
        elif data.get("s") == "old-projects":
            queryset = queryset.old_projects()
        elif data.get("s") == "no-projected-gross-margin":
            queryset = queryset.no_projected_gross_margin()
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

    if request.GET.get("export") == "xlsx" and statistics["statistics"]:
        xlsx = WorkbenchXLSXDocument()
        xlsx.project_budget_statistics(statistics)
        return xlsx.to_response("project-budget-statistics.xlsx")

    return render(
        request,
        "reporting/project_budget_statistics.html",
        {"form": form, "statistics": statistics},
    )


class PlayingBankForm(Form):
    s = forms.ChoiceField(
        choices=[
            ("", _("Open")),
            ("this-year", _("Still open or closed during the current year")),
        ],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
        label="",
    )

    def queryset(self):
        data = self.cleaned_data
        queryset = Project.objects.all()
        if data.get("s") == "":
            queryset = queryset.open()
        elif data.get("s") == "this-year":
            queryset = queryset.filter(
                Q(closed_on__isnull=True)
                | Q(closed_on__gte=dt.date.today().replace(month=1, day=1))
            )
        return queryset.select_related("owned_by")


@filter_form(PlayingBankForm)
def playing_bank_view(request, form):
    statistics = third_party_costs.playing_bank(projects=form.queryset())
    return render(
        request,
        "reporting/playing_bank.html",
        {"form": form, "statistics": statistics},
    )


class DateRangeFilterForm(Form):
    date_from = forms.DateField(
        label=_("Date from"), required=False, widget=DateInput()
    )
    date_until = forms.DateField(
        label=_("Date until"), required=False, widget=DateInput()
    )

    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        data.setdefault("date_from", monday().isoformat())
        data.setdefault("date_until", (monday() + dt.timedelta(days=6)).isoformat())
        super().__init__(data, *args, **kwargs)

        self.fields["date_from"].help_text = format_html(
            "{}: {}",
            _("Set predefined period"),
            format_html_join(
                ", ", '<a href="#" data-set-period="{}:{}">{}</a>', date_ranges()
            ),
        )
        self.fields["date_until"].help_text = format_html(
            "{}: {}",
            _("Set date"),
            format_html_join(
                ", ",
                '<a href="#" data-field-value="{}">{}</a>',
                [(dt.date.today().isoformat(), _("today"))],
            ),
        )


class DateRangeAndTeamFilterForm(DateRangeFilterForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["team"] = forms.TypedChoiceField(
            choices=[
                ("", _("Everyone")),
                [
                    capfirst(Team._meta.verbose_name_plural),
                    [(team.id, str(team)) for team in Team.objects.all()],
                ],
                [
                    capfirst(_("users")),
                    [
                        (-user.id, str(user))
                        for user in User.objects.filter(is_active=True)
                    ],
                ],
                [
                    _("Inactive users"),
                    [
                        (-user.id, str(user))
                        for user in User.objects.filter(is_active=False)
                    ],
                ],
            ],
            label=capfirst(Team._meta.verbose_name),
            required=False,
            coerce=int,
        )

    def users(self):
        data = self.cleaned_data
        queryset = User.objects.all()
        if data.get("team") and data.get("team") > 0:
            queryset = queryset.filter(teams=data.get("team"))
        elif data.get("team") and data.get("team") < 0:
            queryset = queryset.filter(id=-data.get("team"))
        return queryset


@filter_form(DateRangeFilterForm)
def date_range_filter_view(request, form, *, template_name, stats_fn):
    return render(
        request,
        template_name,
        {
            "form": form,
            "stats": stats_fn([
                form.cleaned_data["date_from"],
                form.cleaned_data["date_until"],
            ]),
        },
    )


@filter_form(DateRangeAndTeamFilterForm)
def date_range_and_users_filter_view(request, form, *, template_name, stats_fn):
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


@filter_form(DateRangeFilterForm)
def labor_costs_view(request, form):
    date_range = [form.cleaned_data["date_from"], form.cleaned_data["date_until"]]

    if project := request.GET.get("project"):
        return render(
            request,
            "reporting/labor_costs_by_user.html",
            {
                "stats": labor_costs.labor_costs_by_user(date_range, project=project),
            },
        )
    if cost_center := request.GET.get("cost_center"):
        return render(
            request,
            "reporting/labor_costs_by_user.html",
            {
                "stats": labor_costs.labor_costs_by_user(
                    date_range, cost_center=cost_center
                ),
            },
        )
    if request.GET.get("users"):
        return render(
            request,
            "reporting/labor_costs_by_user.html",
            {"stats": labor_costs.labor_costs_by_user(date_range)},
        )

    return render(
        request,
        "reporting/labor_costs.html",
        {
            "stats": labor_costs.labor_costs_by_cost_center(date_range),
            "date_range": date_range,
            "form": form,
        },
    )


@filter_form(DateRangeFilterForm)
def logging(request, form):
    date_range = [form.cleaned_data["date_from"], form.cleaned_data["date_until"]]

    return render(
        request,
        "reporting/logging.html",
        {"form": form, "logbook_stats": logbook_stats(date_range)},
    )


def work_anniversaries_view(request):
    return render(
        request,
        "reporting/work_anniversaries.html",
        {"work_anniversaries": work_anniversaries()},
    )


def birthdays_view(request):
    return render(
        request,
        "reporting/birthdays.html",
        {"birthdays": birthdays()},
    )
