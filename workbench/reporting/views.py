import datetime as dt
from collections import defaultdict
from decimal import Decimal
from functools import reduce
from itertools import groupby

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import render
from django.utils.text import capfirst
from django.utils.translation import gettext_lazy as _
from more_itertools import chunked

from workbench.accounts.models import Team, User
from workbench.accounts.reporting import (
    average_employment_duration,
    birthdays,
    work_anniversaries,
)
from workbench.deals.reporting import accepted_deals
from workbench.invoices.models import Invoice
from workbench.logbook.models import LoggedCost
from workbench.logbook.reporting import logbook_stats
from workbench.projects.models import Project
from workbench.reporting import (
    green_hours,
    key_data,
    labor_costs,
    project_budget_statistics,
    squeeze,
    third_party_costs,
)
from workbench.reporting.utils import date_ranges
from workbench.tools.charts import bar_chart
from workbench.tools.formats import Z0, Z2, currency, local_date_format
from workbench.tools.forms import DateInput, Form
from workbench.tools.validation import (
    filter_form,
    in_days,
    last_month_range,
    monday,
    month_range,
)
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
            .outstanding(on=self.cleaned_data["cutoff_date"])
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

    open_items = form.open_items_list()
    return render(
        request,
        "reporting/open_items_list.html",
        {
            "form": form,
            "open_items_list": open_items,
            "chart": _open_items_chart(
                list(open_items["list"]), cutoff=form.cleaned_data["cutoff_date"]
            ),
        },
    )


def _open_items_chart(invoices, *, cutoff):
    """Everything overdue on the cutoff date as one bar, then the amounts
    due per week"""
    if not invoices:
        return None
    overdue = sum((i.total_excl_tax for i in invoices if i.due_on < cutoff), Z2)
    due = defaultdict(lambda: Z2)
    for invoice in invoices:
        if invoice.due_on >= cutoff:
            due[monday(invoice.due_on)] += invoice.total_excl_tax
    labels, values = [_("overdue")], [None]
    week = monday(cutoff)
    while due and week <= max(due):
        labels.append(f"KW{week:%V}")
        values.append(due.get(week, Z2))
        week += dt.timedelta(days=7)
    return bar_chart(
        labels,
        bars=[
            {
                "label": _("overdue"),
                "values": [overdue] + [None] * (len(labels) - 1),
                "color": "wb-series-2",
            },
            {"label": _("due"), "values": values, "color": "wb-series-1"},
        ],
        fmt=currency,
        axis_fmt=_amount,
        height=220,
    )


def key_data_details(fn):
    def view(request, year, month):
        return fn(request, month_range(dt.date(int(year), int(month), 1)))

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
            .filter(rendered_on__range=date_range, third_party_costs__isnull=False)
            .order_by("rendered_on", "id")
            .select_related("service"),
            "invoices": Invoice.objects
            .invoiced()
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
            "chart": _projected_gross_margin_chart(all_months, pi["monthly_overall"]),
        },
    )


def _projected_gross_margin_chart(months, monthly):
    """Projected gross margin per month, projections of past months which
    haven't been invoiced in time separately"""
    if not months:
        return None
    today = dt.date.today()
    current = (today.year, today.month)

    def values(*, past):
        return [
            monthly.get(month, Z2) if (month < current) == past else None
            for month in months
        ]

    return bar_chart(
        [local_date_format(dt.date(*month, 1), fmt="M y") for month in months],
        bars=[
            {
                "label": _("overdue"),
                "values": values(past=True),
                "color": "wb-series-2",
            },
            {
                "label": _("projected gross margin"),
                "values": values(past=False),
                "color": "wb-series-1",
            },
        ],
        fmt=currency,
        axis_fmt=_amount,
        height=220,
    )


def _amount(value):
    return f"{value:,.0f}".replace(",", "’")


def _years_chart(labels, years, *, projected=None, height=280):
    """The last year as bars (with the projection on top), the years before
    as lines"""
    if not years:
        return None
    *previous, (year, values) = years
    return bar_chart(
        labels,
        bars=[
            {"label": str(year), "values": values, "color": "wb-series-1"},
            *(
                [
                    {
                        "label": capfirst(_("projected gross margin")),
                        "values": projected,
                        "color": "wb-series-projected",
                    }
                ]
                if projected
                else []
            ),
        ],
        lines=[
            {"label": str(year), "values": values, "color": f"wb-series-{index}"}
            for index, (year, values) in enumerate(reversed(previous), 2)
        ],
        fmt=currency,
        axis_fmt=_amount,
        height=height,
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

    gmp_factor = Decimal("365.24") / (
        1 + Decimal((today - dt.date(today.year, 1, 1)).days)
    )
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

        for key, months_iter in groupby(gh, key=lambda row: row["month"].year):
            this = zero.copy()
            months = list(months_iter)
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
            "invoiced_corrected_chart": _years_chart(
                [local_date_format(dt.date(2000, i, 1), fmt="M") for i in range(1, 13)],
                [
                    (
                        year,
                        [gross_margin_months.get((year, i), Z2) for i in range(1, 13)],
                    )
                    for year in range(date_range[0].year, date_range[1].year + 1)
                ],
                projected=[
                    projected_gross_margin["monthly_overall"].get((today.year, i), Z2)
                    for i in range(1, 13)
                ],
            ),
            "invoiced_corrected_per_fte_chart": _years_chart(
                ["Q1", "Q2", "Q3", "Q4"],
                [
                    (
                        year["year"],
                        [
                            sum(month["margin_per_fte"] or 0 for month in quarter)
                            for quarter in chunked(year["months"], 3)
                        ],
                    )
                    for year in gross_margin_by_years
                ],
                height=200,
            ),
            "green_hours": yearly_headline(gh),
            "hours_distribution_chart": bar_chart(
                [local_date_format(row["month"], fmt="M Y") for row in gh],
                bars=[
                    {
                        "label": label,
                        "values": [100 * row[attribute] / row["total"] for row in gh],
                        "color": color,
                    }
                    for label, attribute, color in [
                        (_("profitable"), "profitable", "wb-series-3"),
                        (_("maintenance"), "maintenance", "wb-series-1"),
                        (_("overdrawn"), "overdrawn", "wb-series-2"),
                        (_("internal"), "internal", "wb-series-neutral"),
                    ]
                ],
                fmt=lambda value: f"{value:.0f}%",
                maximum=100,
            ),
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
        if data.get("s") == "":  # noqa: PLC1901
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

    def periods(self):
        """Predefined periods offered next to the date fields"""
        return date_ranges()

    def today(self):
        return dt.date.today().isoformat()


class LastMonthDateRangeFilterForm(DateRangeFilterForm):
    def __init__(self, data, *args, **kwargs):
        data = data.copy()
        date_from, date_until = last_month_range()
        data.setdefault("date_from", date_from.isoformat())
        data.setdefault("date_until", date_until.isoformat())
        super().__init__(data, *args, **kwargs)


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


@filter_form(DateRangeFilterForm)
def accepted_deals_view(request, form):
    date_range = [form.cleaned_data["date_from"], form.cleaned_data["date_until"]]
    stats = accepted_deals(date_range)
    return render(
        request,
        "reporting/accepted_deals.html",
        {
            "form": form,
            "stats": stats,
            "chart": _accepted_deals_chart(stats, date_range),
        },
    )


def _accepted_deals_chart(stats, date_range):
    """Accepted deals per month and value type, and the target of the days
    of each month within the date range"""
    months = []
    month = date_range[0].replace(day=1)
    while month <= date_range[1]:
        months.append(month)
        month = (month + dt.timedelta(days=32)).replace(day=1)
    # Monthly bars of a week or a single month say nothing, and the targets
    # of months cut off by the date range look strange.
    complete = [
        month
        for month in months
        if month >= date_range[0] and month_range(month)[1] <= date_range[1]
    ]
    if len(complete) < 2 or len(months) > 36:
        return None

    values = {
        row["month"]: {value["type"]: value["value"] for value in row["values"]}
        for row in stats["by_month_and_valuetype"]
    }
    weekly_target = sum(
        (type.weekly_target or 0 for type in stats["valuetypes"]), Decimal(0)
    )

    def target(month):
        first = max(month, date_range[0])
        last = min(month_range(month)[1], date_range[1])
        return weekly_target * ((last - first).days + 1) / 7

    return bar_chart(
        [local_date_format(month, fmt="M y") for month in months],
        bars=[
            {
                "label": str(type),
                "values": [values.get(month, {}).get(type, Z2) for month in months],
                "color": f"wb-series-{index}",
            }
            for index, type in enumerate(stats["valuetypes"], 1)
        ],
        lines=[
            {
                "label": capfirst(_("target")),
                "values": [target(month) for month in months],
                "color": "wb-series-muted",
                "dashed": True,
            }
        ]
        if weekly_target
        else [],
        fmt=currency,
        axis_fmt=_amount,
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
                "date_range": date_range,
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
                "date_range": date_range,
            },
        )
    if request.GET.get("users"):
        return render(
            request,
            "reporting/labor_costs_by_user.html",
            {
                "stats": labor_costs.labor_costs_by_user(date_range),
                "date_range": date_range,
            },
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


@filter_form(LastMonthDateRangeFilterForm)
def squeeze_view(request, form):
    date_range = [form.cleaned_data["date_from"], form.cleaned_data["date_until"]]

    cutoff = (date_range[1].replace(day=1) + dt.timedelta(days=32)).replace(day=9)
    if dt.date.today() < cutoff:
        messages.warning(
            request,
            _(
                "Invoices for the selected period may not be complete yet"
                " (cutoff: %(cutoff)s)."
            )
            % {"cutoff": local_date_format(cutoff)},
        )

    data = squeeze.squeeze_data(date_range)

    if request.GET.get("export") == "xlsx":
        xlsx = squeeze.build_xlsx(data)
        return xlsx.to_response(f"squeeze-{date_range[0]}-{date_range[1]}.xlsx")

    return render(
        request,
        "reporting/squeeze.html",
        {
            "form": form,
            "data": data,
            "BASE_HOURLY_RATE": squeeze.BASE_HOURLY_RATE,
        },
    )
