from django.conf.urls import url

from workbench.accounts.features import FEATURES, controlling_only, feature_required
from workbench.awt.views import ReportView
from workbench.circles.reporting import hours_by_circle
from workbench.projects.reporting import hours_per_customer
from workbench.reporting.views import (
    green_hours_view,
    hours_filter_view,
    key_data_view,
    open_items_list,
    overdrawn_projects_view,
    project_budget_statistics_view,
)


urlpatterns = [
    url(r"^annual-working-time/$", ReportView.as_view(), name="awt_year_report"),
    url(
        r"^overdrawn-projects/$",
        overdrawn_projects_view,
        name="report_overdrawn_projects",
    ),
    url(
        r"^open-items-list/$",
        controlling_only(open_items_list),
        name="report_open_items_list",
    ),
    url(r"^key-data/$", controlling_only(key_data_view), name="report_key_data"),
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
    url(r"^green-hours/$", green_hours_view, name="report_green_hours"),
]
