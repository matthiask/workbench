from django.urls import path, re_path

from workbench.accounts.features import (
    FEATURES,
    controlling_only,
    deals_only,
    feature_required,
    labor_costs_only,
)
from workbench.awt.views import absence_calendar, annual_working_time_view
from workbench.circles.reporting import hours_by_circle, hours_per_work_category
from workbench.deals.reporting import accepted_deals, deal_history, declined_deals
from workbench.planning.reporting import planning_vs_logbook
from workbench.projects.reporting import hours_per_customer
from workbench.reporting.green_hours import green_hours
from workbench.reporting.views import (
    birthdays_view,
    hours_filter_view,
    key_data_gross_profit,
    key_data_projected_invoices,
    key_data_third_party_costs,
    key_data_view,
    labor_costs_view,
    logging,
    open_items_list,
    overdrawn_projects_view,
    project_budget_statistics_view,
    work_anniversaries_view,
)


urlpatterns = [
    path("absence-calendar/", absence_calendar, name="awt_absence_calendar"),
    path("annual-working-time/", annual_working_time_view, name="awt_year_report"),
    path(
        "overdrawn-projects/",
        controlling_only(overdrawn_projects_view),
        name="report_overdrawn_projects",
    ),
    path(
        "open-items-list/",
        controlling_only(open_items_list),
        name="report_open_items_list",
    ),
    path("key-data/", controlling_only(key_data_view), name="report_key_data"),
    re_path(
        r"^key-data/gross-profit/(?P<year>[0-9]{4})\.(?P<month>[0-9]{1,2})/$",
        controlling_only(key_data_gross_profit),
    ),
    re_path(
        r"^key-data/third-party-costs/(?P<year>[0-9]{4})\.(?P<month>[0-9]{1,2})/$",
        controlling_only(key_data_third_party_costs),
    ),
    re_path(
        r"^key-data/projected-invoices/",
        controlling_only(key_data_projected_invoices),
    ),
    path(
        "hours-per-customer/",
        hours_filter_view,
        {
            "template_name": "reporting/hours_per_customer.html",
            "stats_fn": hours_per_customer,
        },
        name="report_hours_per_customer",
    ),
    path(
        "planning-vs-logbook/",
        hours_filter_view,
        {
            "template_name": "reporting/planning_vs_logbook.html",
            "stats_fn": planning_vs_logbook,
        },
        name="report_planning_vs_logbook",
    ),
    path(
        "hours-by-circle/",
        feature_required(FEATURES.GLASSFROG)(hours_filter_view),
        {
            "template_name": "reporting/hours_by_circle.html",
            "stats_fn": hours_by_circle,
        },
        name="report_hours_by_circle",
    ),
    path(
        "hours-per-work-category/",
        feature_required(FEATURES.GLASSFROG)(hours_filter_view),
        {
            "template_name": "reporting/hours_per_work_category.html",
            "stats_fn": hours_per_work_category,
        },
        name="report_hours_per_work_category",
    ),
    path(
        "project-budget-statistics/",
        controlling_only(project_budget_statistics_view),
        name="report_project_budget_statistics",
    ),
    path(
        "green-hours/",
        controlling_only(hours_filter_view),
        {"template_name": "reporting/green_hours.html", "stats_fn": green_hours},
        name="report_green_hours",
    ),
    path(
        "accepted-deals/",
        deals_only(hours_filter_view),
        {"template_name": "reporting/accepted_deals.html", "stats_fn": accepted_deals},
        name="report_accepted_deals",
    ),
    path(
        "accepted-deals/deals/",
        deals_only(hours_filter_view),
        {
            "template_name": "reporting/accepted_deals_for_user.html",
            "stats_fn": accepted_deals,
        },
    ),
    path(
        "declined-deals/",
        deals_only(hours_filter_view),
        {"template_name": "reporting/declined_deals.html", "stats_fn": declined_deals},
        name="report_declined_deals",
    ),
    path(
        "deal-history/",
        deals_only(hours_filter_view),
        {"template_name": "reporting/deal_history.html", "stats_fn": deal_history},
        name="report_deal_history",
    ),
    path("labor-costs/", labor_costs_only(labor_costs_view), name="report_labor_costs"),
    path("logging/", controlling_only(logging), name="report_logging"),
    path(
        "work-anniversaries/",
        work_anniversaries_view,
        name="report_work_anniversaries",
    ),
    path(
        "birthdays/",
        birthdays_view,
        name="report_birthdays",
    ),
]
