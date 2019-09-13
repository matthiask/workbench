from django.conf.urls import url

from workbench.awt.views import ReportView
from workbench.reporting.views import (
    green_hours_view,
    hours_by_circle_view,
    hours_per_customer_view,
    key_data_view,
    monthly_invoicing_view,
    open_items_list,
    overdrawn_projects_view,
    project_budget_statistics_view,
)


urlpatterns = [
    url(r"^annual-working-time/$", ReportView.as_view(), name="awt_year_report"),
    url(
        r"^monthly-invoicing/$", monthly_invoicing_view, name="report_monthly_invoicing"
    ),
    url(
        r"^overdrawn-projects/$",
        overdrawn_projects_view,
        name="report_overdrawn_projects",
    ),
    url(r"^open-items-list/$", open_items_list, name="report_open_items_list"),
    url(r"^hours-by-circle/$", hours_by_circle_view, name="report_hours_by_circle"),
    url(r"^key-data/$", key_data_view, name="report_key_data"),
    url(
        r"^hours-per-customer/$",
        hours_per_customer_view,
        name="report_hours_per_customer",
    ),
    url(
        r"^project-budget-statistics/$",
        project_budget_statistics_view,
        name="report_project_budget_statistics",
    ),
    url(r"^green-hours/$", green_hours_view, name="report_green_hours"),
]
