from django.conf.urls import url

from workbench.accounts.features import (
    FEATURES,
    controlling_only,
    feature_required,
    labor_costs_only,
)
from workbench.awt.views import absence_calendar, annual_working_time_view
from workbench.circles.reporting import hours_by_circle
from workbench.projects.reporting import hours_per_customer
from workbench.reporting.green_hours import green_hours
from workbench.reporting.views import (
    hours_filter_view,
    key_data_gross_profit,
    key_data_third_party_costs,
    key_data_view,
    labor_costs_view,
    open_items_list,
    overdrawn_projects_view,
    project_budget_statistics_view,
)


urlpatterns = [
    url(r"^absence-calendar/$", absence_calendar, name="awt_absence_calendar"),
    url(r"^annual-working-time/$", annual_working_time_view, name="awt_year_report"),
    url(
        r"^overdrawn-projects/$",
        controlling_only(overdrawn_projects_view),
        name="report_overdrawn_projects",
    ),
    url(
        r"^open-items-list/$",
        controlling_only(open_items_list),
        name="report_open_items_list",
    ),
    url(r"^key-data/$", controlling_only(key_data_view), name="report_key_data"),
    url(
        r"^key-data/gross-profit/(?P<year>[0-9]{4})\.(?P<month>[0-9]{1,2})/$",
        controlling_only(key_data_gross_profit),
    ),
    url(
        r"^key-data/third-party-costs/(?P<year>[0-9]{4})\.(?P<month>[0-9]{1,2})/$",
        controlling_only(key_data_third_party_costs),
    ),
    url(
        r"^hours-per-customer/$",
        hours_filter_view,
        {
            "template_name": "reporting/hours_per_customer.html",
            "stats_fn": hours_per_customer,
        },
        name="report_hours_per_customer",
    ),
    url(
        r"^hours-by-circle/$",
        feature_required(FEATURES.GLASSFROG)(hours_filter_view),
        {
            "template_name": "reporting/hours_by_circle.html",
            "stats_fn": hours_by_circle,
        },
        name="report_hours_by_circle",
    ),
    url(
        r"^project-budget-statistics/$",
        controlling_only(project_budget_statistics_view),
        name="report_project_budget_statistics",
    ),
    url(
        r"^green-hours/$",
        controlling_only(hours_filter_view),
        {"template_name": "reporting/green_hours.html", "stats": green_hours},
        name="report_green_hours",
    ),
    url(
        r"^labor-costs/$", labor_costs_only(labor_costs_view), name="report_labor_costs"
    ),
]
