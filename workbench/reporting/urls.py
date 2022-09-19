from django.urls import path, re_path

from workbench.accounts.features import controlling_only, deals_only, labor_costs_only
from workbench.awt.views import absence_calendar, annual_working_time_view
from workbench.deals.reporting import accepted_deals, deal_history, declined_deals
from workbench.planning.reporting import planning_vs_logbook
from workbench.projects.reporting import hours_per_customer, hours_per_type
from workbench.reporting.green_hours import green_hours
from workbench.reporting.views import (
    birthdays_view,
    date_range_and_users_filter_view,
    date_range_filter_view,
    key_data_gross_profit,
    key_data_third_party_costs,
    key_data_view,
    labor_costs_view,
    logging,
    open_items_list,
    playing_bank_view,
    project_budget_statistics_view,
    projected_gross_margin,
    work_anniversaries_view,
)


urlpatterns = [
    path("absence-calendar/", absence_calendar, name="awt_absence_calendar"),
    path("annual-working-time/", annual_working_time_view, name="awt_year_report"),
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
        r"^projected-gross-margin/",
        controlling_only(projected_gross_margin),
        name="report_projected_gross_margin",
    ),
    path(
        "hours-per-customer/",
        date_range_and_users_filter_view,
        {
            "template_name": "reporting/hours_per_customer.html",
            "stats_fn": hours_per_customer,
        },
        name="report_hours_per_customer",
    ),
    path(
        "hours-per-type/",
        controlling_only(date_range_and_users_filter_view),
        {"template_name": "reporting/hours_per_type.html", "stats_fn": hours_per_type},
        name="report_hours_per_type",
    ),
    path(
        "planning-vs-logbook/",
        date_range_and_users_filter_view,
        {
            "template_name": "reporting/planning_vs_logbook.html",
            "stats_fn": planning_vs_logbook,
        },
        name="report_planning_vs_logbook",
    ),
    path(
        "project-budget-statistics/",
        controlling_only(project_budget_statistics_view),
        name="report_project_budget_statistics",
    ),
    path(
        "playing-bank/",
        controlling_only(playing_bank_view),
        name="report_third_party_costs",
    ),
    path(
        "green-hours/",
        controlling_only(date_range_and_users_filter_view),
        {"template_name": "reporting/green_hours.html", "stats_fn": green_hours},
        name="report_green_hours",
    ),
    path(
        "accepted-deals/",
        deals_only(date_range_filter_view),
        {"template_name": "reporting/accepted_deals.html", "stats_fn": accepted_deals},
        name="report_accepted_deals",
    ),
    path(
        "accepted-deals/deals/",
        deals_only(date_range_and_users_filter_view),
        {
            "template_name": "reporting/accepted_deals_for_user.html",
            "stats_fn": accepted_deals,
        },
    ),
    path(
        "declined-deals/",
        deals_only(date_range_filter_view),
        {"template_name": "reporting/declined_deals.html", "stats_fn": declined_deals},
        name="report_declined_deals",
    ),
    path(
        "deal-history/",
        deals_only(date_range_and_users_filter_view),
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
