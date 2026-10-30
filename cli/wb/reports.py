"""Reports"""

import click

from wb.core import (
    _amount,
    _bool,
    _complete_short_names,
    _days,
    _echo_csv,
    _echo_fields,
    _echo_invoice_list,
    _echo_json,
    _echo_period,
    _hours,
    _link,
    _number,
    _percentage,
    _period_options,
    _period_params,
    _request,
    _table,
    _users_options,
    _without,
    cli,
    console,
)


@cli.group()
def reports():
    """Reports, most of them require the controlling feature"""


@reports.command("key-data")
@click.option("--month", help="Month like 2026-09, defaults to the last month.")
@click.option("--json", "as_json", is_flag=True)
def key_data(month, as_json):
    """Key data of a month: Gross margin, green hours, deals etc."""
    data = _request(
        "GET", "reports/key-data/", params={"month": month} if month else {}
    )
    if as_json:
        _echo_json(data)
        return
    _echo_fields(
        f"Key data {data['month']}",
        [
            ("Gross margin", _amount(data["gross_margin"])),
            ("Squeeze gross margin", _amount(data["squeeze_gross_margin"])),
            ("Full-time equivalents", _number(data["full_time_equivalents"], 2)),
            ("Green hours", _percentage(data["green_hours_percentage"])),
            ("Open invoices excl. tax", _amount(data["open_invoices_total_excl_tax"])),
            ("Canceled invoices", _amount(data["canceled_invoices_total_excl_tax"])),
            ("Accruals", _amount(data["accruals"])),
        ],
    )
    table = _table("Month", "Green hours>", "Canceled invoices>", title="Before")
    for row in data["previous_months"]:
        table.add_row(
            row["month"],
            _percentage(row["green_hours_percentage"]),
            _amount(row["canceled_invoices_total_excl_tax"]),
        )
    console.print(table)
    funnel = data["deals_funnel"]
    table = _table("Deals", "Value>", title="Deals funnel")
    for label, key in [
        ("High probability, next 4 weeks", "high_probability_next_4_weeks"),
        ("High probability, next 12 weeks", "high_probability_next_12_weeks"),
        ("High probability, later", "high_probability_later"),
        ("Normal probability", "normal_probability"),
    ]:
        table.add_row(label, _amount(funnel[key]))
    console.print(table)
    if data["accepted_deals"]:
        table = _table("Closed on", "Title", "Customer", "Value>", title="Accepted")
        for deal in data["accepted_deals"]:
            table.add_row(
                deal["closed_on"],
                deal["title"],
                deal["customer"],
                _amount(deal["value"]),
            )
        console.print(table)


@reports.command("cash-data")
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Cutoff date, defaults to today.",
)
@click.option("--json", "as_json", is_flag=True)
def cash_data(date, as_json):
    """Cash data: Open invoices, planned invoicing, accruals etc.

    Planned invoicing, accepted offers and work which hasn't been invoiced
    are only available for the current week."""
    params = {"date": date.date().isoformat()} if date else {}
    data = _request("GET", "reports/cash-data/", params=params)
    if as_json:
        _echo_json(data)
        return
    open_invoices = data["open_invoices"]
    offers = data["accepted_offers_not_invoiced"] or {}
    work = data["work_not_invoiced"] or {}
    _echo_fields(
        f"Cash data {data['date']} ({data['currency']})",
        [
            ("Open invoices excl. tax", _amount(open_invoices["total_excl_tax"])),
            ("Open invoices incl. tax", _amount(open_invoices["total_incl_tax"])),
            ("Overdue incl. tax", _amount(open_invoices["overdue_incl_tax"])),
            ("Accruals", _amount(data["accruals"])),
            ("Work not invoiced", _amount(work.get("total_excl_tax"))),
            ("  beyond the offers", _amount(work.get("beyond_offers_excl_tax"))),
            (
                "  in planned invoicing",
                _amount(work.get("in_planned_invoicing_excl_tax")),
            ),
            ("Accepted offers not invoiced", _amount(offers.get("total_excl_tax"))),
            (
                "  not in planned invoicing (gross margin)",
                _amount(offers.get("not_in_planned_invoicing_excl_tax")),
            ),
            (
                "Planned invoicing overdue",
                _amount(data["planned_invoicing_overdue_excl_tax"]),
            ),
        ],
    )
    if data["planned_invoicing_by_month"]:
        table = _table("Month", "Gross margin>", title="Planned invoicing")
        for row in data["planned_invoicing_by_month"]:
            table.add_row(row["month"], _amount(row["amount_excl_tax"]))
        console.print(table)
    table = _table("Week", "Excl. tax>", "Incl. tax>", title="Receivables by due week")
    for row in data["receivables_by_due_week"]:
        table.add_row(
            f"{row['iso_year']}-W{row['iso_week']:02d}",
            _amount(row["amount_excl_tax"]),
            _amount(row["amount_incl_tax"]),
        )
    console.print(table)


@reports.command("working-time")
@click.option("--year", type=int, help="Defaults to the current year.")
@click.option(
    "--user", help="Short name, defaults to you.", shell_complete=_complete_short_names
)
@click.option(
    "--all",
    "all_",
    is_flag=True,
    help="Everyone employed during the year, requires the controlling feature.",
)
@click.option("--weekly", is_flag=True, help="Show the hours per week.")
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def working_time(year, user, all_, weekly, as_csv, as_json):
    """Annual working time: Target, logged hours, absences and balance

    The balance per week compares the working time to a target based on the
    working time per day, the employment and the holidays."""
    params = {
        "year": year,
        "user": user,
        "all": _bool(all_) if all_ else None,
        "weekly": _bool(weekly) if weekly else None,
    }
    data = _request(
        "GET",
        "reports/working-time/",
        params={key: value for key, value in params.items() if value},
    )
    if as_csv:
        _echo_csv([
            {"user": row["user"]} | entry
            for row in data["users"]
            for entry in (row["weeks"] if weekly else row["months"])
        ])
        return
    if as_json:
        _echo_json(data)
        return
    for warning in data["warnings"]:
        click.secho(warning, fg="yellow", err=True)
    for row in data["users"]:
        console.print(f"{row['user']} {data['year']}", style="bold")
        totals = row["totals"]
        if weekly:
            table = _table(
                "Week", "Target>", "Logged>", "Absences>", "Balance>", "Running>"
            )
            for week in row["weeks"]:
                table.add_row(
                    week["week"],
                    _hours(week["target"]),
                    _hours(week["hours"]),
                    _hours(week["absences"]),
                    _hours(week["delta"]),
                    _hours(week["running_delta"]),
                )
            console.print(table)
            continue
        table = _table(
            "Month",
            "Employment>",
            "Target>",
            "Logged>",
            "Absences>",
            "Working time>",
            "Balance>",
            "Running>",
            "Vacation days>",
            "Sick days>",
            show_footer=True,
        )
        for month in row["months"]:
            table.add_row(
                month["month"],
                _percentage(month["percentage"]),
                _hours(month["target"]),
                _hours(month["hours"]),
                _hours(month["absences_time"]),
                _hours(month["working_time"]),
                _hours(month["balance"]),
                _hours(month["running_balance"]),
                _days(month["vacation_days"]),
                _days(month["sickness_days"]),
            )
        table.columns[0].footer = "Total"
        table.columns[1].footer = _percentage(totals["percentage"])
        table.columns[2].footer = _hours(totals["target"])
        table.columns[3].footer = _hours(totals["hours"])
        table.columns[4].footer = _hours(totals["absences_time"])
        table.columns[5].footer = _hours(totals["working_time"])
        table.columns[6].footer = _hours(totals["running_sum"])
        table.columns[8].footer = _days(totals["absence_vacation"])
        table.columns[9].footer = _days(totals["absence_sickness"])
        console.print(table)
        console.print(
            f"Vacation days: {_days(totals['available_vacation_days'])} available,"
            f" {_days(totals['vacation_days_credit'])} left"
        )
        console.print(
            f"Balance incl. vacation days left: {_hours(totals['balance'])}h"
            f" ({totals['balance_days']} days)",
            style="bold",
        )
        console.print()


@reports.command("projected-gross-margin")
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def projected_gross_margin(as_csv, as_json):
    """Planned invoicing of open projects which hasn't been invoiced yet"""
    data = _request("GET", "reports/projected-gross-margin/")
    if as_csv:
        _echo_csv(data["projects"])
        return
    if as_json:
        _echo_json(data)
        return
    table = _table("Month", "Gross margin>", show_footer=True)
    for month, value in data["monthly"].items():
        table.add_row(month, _amount(value))
    table.columns[0].footer = "Total"
    table.columns[1].footer = _amount(sum(map(float, data["monthly"].values())))
    console.print(table)
    table = _table("Code", "Title", "Owner", "Projected>", "Invoiced>", "Not invoiced>")
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            row["owned_by"],
            _amount(row["projected_total"]),
            _amount(row["gross_margin"]),
            _amount(row["not_invoiced"]),
        )
    console.print(table)


@reports.command("budget")
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Cutoff date, defaults to today.",
)
@click.option(
    "--owned-by",
    help="Short name, or 'inactive' for inactive users.",
    shell_complete=_complete_short_names,
)
@click.option("--internal", is_flag=True, help="Internal projects only.")
@click.option("--closed", is_flag=True, help="Projects closed during the last year.")
@click.option(
    "--filter",
    "filter_",
    type=click.Choice([
        "no-invoices",
        "maintenance",
        "old-projects",
        "no-projected-gross-margin",
    ]),
)
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def budget(date, owned_by, internal, closed, filter_, as_csv, as_json):
    """Project budget statistics: Logged work compared to offers and invoices

    Delta is the logbook minus the invoiced amount, positive for work which
    hasn't been invoiced yet."""
    params = {
        "owned_by": owned_by,
        "internal": _bool(internal) if internal else None,
        "closed": _bool(closed) if closed else None,
        "filter": filter_,
    }
    if date:
        params["date"] = date.date().isoformat()
    data = _request(
        "GET",
        "reports/budget/",
        params={key: value for key, value in params.items() if value},
    )
    if as_csv:
        _echo_csv(data["projects"])
        return
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Code",
        "Title",
        "Owner",
        "Offered h>",
        "Logged h>",
        "Logbook>",
        "Sold>",
        "Invoiced>",
        "Delta>",
        "Projected>",
        show_footer=True,
    )
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            row["owned_by"],
            _hours(row["service_hours"]),
            _hours(row["hours"]),
            _amount(row["logbook"]),
            _amount(row["sold"]),
            _amount(row["invoiced"]),
            _amount(row["delta"]),
            _amount(row["projected_gross_margin"]),
        )
    overall = data["overall"]
    table.columns[0].footer = "Total"
    for index, key, fmt in [
        (3, "service_hours", _hours),
        (4, "hours", _hours),
        (5, "logbook", _amount),
        (6, "sold", _amount),
        (7, "invoiced", _amount),
        (9, "projected_gross_margin", _amount),
    ]:
        table.columns[index].footer = fmt(overall[key])
    console.print(table)
    console.print(
        f"Not invoiced yet: {_amount(overall['delta_positive'])},"
        f" accruals: {_amount(overall['delta_negative'])}"
    )


@reports.command("third-party-costs")
@click.option(
    "--this-year",
    is_flag=True,
    help="Also projects closed during the current year.",
)
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def third_party_costs(this_year, as_csv, as_json):
    """Third party costs logged and invoiced per project

    Delta is positive for costs which haven't been invoiced yet."""
    data = _request(
        "GET",
        "reports/third-party-costs/",
        params={"this_year": _bool(this_year)} if this_year else {},
    )
    if as_csv:
        _echo_csv(data["projects"])
        return
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Code",
        "Title",
        "Owner",
        "Offered>",
        "Logged>",
        "Logged (future)>",
        "Invoiced>",
        "Delta>",
        show_footer=True,
    )
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            row["owned_by"],
            _amount(row["offered"]),
            _amount(row["logged"]["past"]),
            _amount(row["logged"]["future"]),
            _amount(row["invoiced"]),
            _amount(row["delta"]),
        )
    table.columns[0].footer = "Total"
    table.columns[3].footer = _amount(data["total_offered"])
    table.columns[4].footer = _amount(data["total_logged"]["past"])
    table.columns[5].footer = _amount(data["total_logged"]["future"])
    table.columns[6].footer = _amount(data["total_invoiced"])
    console.print(table)
    console.print(
        f"Not invoiced yet: {_amount(data['total_not_invoiced'])},"
        f" invoiced too much: {_amount(data['total_invoiced_too_much'])}"
    )


@reports.command("open-items")
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Cutoff date, defaults to today.",
)
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def open_items(date, as_csv, as_json):
    """Invoices sent but not paid on the cutoff date"""
    data = _request(
        "GET",
        "reports/open-items/",
        params={"date": date.date().isoformat()} if date else {},
    )
    if as_csv:
        _echo_csv(data["invoices"])
        return
    if as_json:
        _echo_json(data)
        return
    _echo_invoice_list(data["invoices"])
    table = _table("Due in the week of", "Total excl. tax>", "Total>")
    for week in data["weeks"]:
        table.add_row(
            week["week"], _amount(week["total_excl_tax"]), _amount(week["total"])
        )
    console.print(table)
    console.print(
        f"Total excl. tax: {_amount(data['total_excl_tax'])},"
        f" total: {_amount(data['total'])}"
    )


@reports.command("hours-per-customer")
@_period_options("defaults to this week")
@_users_options
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def hours_per_customer(period, since, until, users, team, as_csv, as_json):
    """Logged hours per customer and user"""
    data = _request(
        "GET",
        "reports/hours-per-customer/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_csv:
        _echo_csv(data["customers"])
        return
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "Customer", "Total>", *(f"{user}>" for user in data["users"]), show_footer=True
    )
    for row in data["customers"]:
        table.add_row(
            _link(row["customer"]["name"], row["customer"]["url"]),
            _hours(row["total_hours"]),
            *(_hours(row["users"].get(user)) for user in data["users"]),
        )
    table.columns[0].footer = "Total"
    table.columns[1].footer = _hours(data["total_hours"])
    for index, hours in enumerate(data["users"].values(), 2):
        table.columns[index].footer = _hours(hours)
    console.print(table)


@reports.command("hours-per-type")
@_period_options("defaults to this week")
@_users_options
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def hours_per_type(period, since, until, users, team, as_csv, as_json):
    """Logged hours per user, external and per internal type

    Shows the percentage reached and expected (in parentheses)."""
    data = _request(
        "GET",
        "reports/hours-per-type/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_csv:
        _echo_csv([
            row | {"types": {type["type"]: type["hours"] for type in row["types"]}}
            for row in data["users"]
        ])
        return
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    types = (
        [type["type"] for type in data["users"][0]["types"]] if data["users"] else []
    )
    table = _table("User", "Total>", *(f"{type}>" for type in types))
    for row in data["users"]:
        table.add_row(
            row["user"],
            _hours(row["total"]),
            *(
                f"{_hours(type['hours'])} {_percentage(type['reached_percentage'])}"
                f" ({_percentage(type['expected_percentage'])})"
                for type in row["types"]
            ),
        )
    console.print(table)


@reports.command("green-hours")
@_period_options("defaults to this week")
@_users_options
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def green_hours(period, since, until, users, team, as_csv, as_json):
    """Profitable, overdrawn, maintenance and internal hours per user

    Green hours are profitable and maintenance hours."""
    data = _request(
        "GET",
        "reports/green-hours/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_csv:
        _echo_csv(data["users"])
        return
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "User",
        "Profitable>",
        "Overdrawn>",
        "Maintenance>",
        "Internal>",
        "Total>",
        "Green>",
        show_footer=True,
    )

    def cells(row):
        return [
            _hours(row["profitable"]),
            _hours(row["overdrawn"]),
            _hours(row["maintenance"]),
            _hours(row["internal"]),
            _hours(row["total"]),
            _percentage(row["percentage"]),
        ]

    for row in data["users"]:
        table.add_row(row["user"], *cells(row))
    if data["total"]:
        table.columns[0].footer = "Total"
        for index, value in enumerate(cells(data["total"]), 1):
            table.columns[index].footer = value
    console.print(table)


@reports.command("planning-vs-logbook")
@_period_options("defaults to this week")
@_users_options
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def planning_vs_logbook(period, since, until, users, team, as_csv, as_json):
    """Planned and logged hours per customer

    The allocation is the customer's share of the logged hours relative to
    its share of the planned hours."""
    data = _request(
        "GET",
        "reports/planning-vs-logbook/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_csv:
        _echo_csv([_without(row, "weeks") for row in data["customers"]])
        return
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "Customer", "Planned>", "Logged>", "Diff>", "Allocation>", show_footer=True
    )
    for row in data["customers"]:
        table.add_row(
            _link(row["customer"]["name"], row["customer"]["url"]),
            _hours(row["planned"]),
            _hours(row["logged"]),
            _hours(row["diff"]),
            _percentage(row["allocation"]),
        )
    table.columns[0].footer = "Total"
    table.columns[1].footer = _hours(data["planned"])
    table.columns[2].footer = _hours(data["logged"])
    table.columns[3].footer = _hours(data["diff"])
    table.columns[4].footer = _percentage(data["logged_percentage"])
    console.print(table)


@reports.command("logging")
@_period_options("defaults to this week")
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def logging_report(period, since, until, as_csv, as_json):
    """How and when users log their hours, and insufficient breaks"""
    data = _request(
        "GET", "reports/logging/", params=_period_params(period, since, until)
    )
    if as_csv:
        _echo_csv(data["users"])
        return
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "User",
        "Entries>",
        "Hours>",
        "Per entry>",
        "Delay>",
        "Logging",
        "Breaks too short>",
    )
    for row in data["users"]:
        breaks = row["insufficient_breaks"]
        table.add_row(
            row["user"],
            str(row["logged_hours"]["count"]),
            _hours(row["logged_hours"]["sum"]),
            _hours(row["logged_hours"]["avg"]),
            f"{_number(row['mean_logging_delay_hours'], 0)}h",
            row["logging"],
            f"{len(breaks['days'])}/{breaks['of']} days",
            style="red" if breaks["warning"] else None,
        )
    console.print(table)


@reports.command("squeeze")
@_period_options("defaults to the last month")
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def squeeze(period, since, until, as_csv, as_json):
    """Gross margin per user and project, requires the productivity feature

    Projects' gross margins are split between users by hours weighted with
    the hourly rate. The delta compares the gross margin to the expected
    gross margin."""
    data = _request(
        "GET", "reports/squeeze/", params=_period_params(period, since, until)
    )
    if as_csv:
        _echo_csv([_without(row, "projects") for row in data["users"]])
        return
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    if data["may_be_incomplete"]:
        click.secho(
            "Invoices for the selected period may not be complete yet.",
            fg="yellow",
            err=True,
        )
    table = _table(
        "User",
        "Hours>",
        "Gross margin>",
        "Rate>",
        "Expected>",
        "Delta>",
        "External>",
        show_footer=True,
    )

    def cells(row):
        return [
            _hours(row["hours_in_range"]),
            _amount(row["gross_margin"]),
            _amount(row["rate"]),
            _amount(row["expected_gross_margin"]),
            _amount(row["delta"]),
            _percentage(row["external_percentage"]),
        ]

    for row in data["users"]:
        table.add_row(row["user"], *cells(row))
    table.columns[0].footer = "Total"
    for index, value in enumerate(cells(data["totals"]), 1):
        table.columns[index].footer = value
    console.print(table)
    table = _table("Code", "Title", "Hours>", "Gross margin>", "Rate>", "Users")
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            _hours(row["hours_in_range"]),
            _amount(row["gross_margin_in_range"]),
            _amount(row["rate"]),
            ", ".join(row["users"]),
        )
    console.print(table)
