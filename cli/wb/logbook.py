"""Logged hours and costs"""

import click

from wb.core import (
    _bool,
    _complete_short_names,
    _echo_csv,
    _echo_json,
    _echo_more,
    _link,
    _page_options,
    _page_params,
    _period_options,
    _period_params,
    _request,
    _table,
    cli,
    console,
)


@cli.group()
def hours():
    """Look at logged hours, log them in Workbench"""


@hours.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.", shell_complete=_complete_short_names)
@_period_options("filters the date the work was done")
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_hours(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search logged hours, newest first"""
    params = {"q": " ".join(query)}
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    params |= _period_params(period, since, until)
    data = _request(
        "GET", "logbook/hours/", params=params | _page_params(limit, offset)
    )
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Rendered on",
        "By",
        "Project",
        "Service",
        "Hours>",
        "Description",
        show_footer=True,
    )
    for row in data["items"]:
        table.add_row(
            _link(row["rendered_on"], row["url"]),
            row["rendered_by"],
            _link(row["project"]["code"], row["project"]["url"]),
            row["service"],
            row["hours"],
            row["description"],
        )
    table.columns[0].footer = "Total"
    table.columns[4].footer = data["total_hours"]
    console.print(table)
    _echo_more(data, offset, "entries", note="The total includes all of them.")


@cli.group()
def costs():
    """Look at logged costs, log them in Workbench"""


@costs.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.", shell_complete=_complete_short_names)
@click.option("--expenses", is_flag=True, help="Paid from someone's own pocket.")
@_period_options("filters the date the work was done")
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_costs(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    expenses,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search logged costs, newest first"""
    params = {"q": " ".join(query), "expenses": _bool(expenses)}
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    params |= _period_params(period, since, until)
    data = _request(
        "GET", "logbook/costs/", params=params | _page_params(limit, offset)
    )
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Rendered on",
        "By",
        "Project",
        "Service",
        "Cost>",
        "Third party>",
        "Description",
        show_footer=True,
    )
    for row in data["items"]:
        table.add_row(
            _link(row["rendered_on"], row["url"]),
            row["rendered_by"],
            _link(row["project"]["code"], row["project"]["url"]),
            row["service"],
            row["cost"],
            row["third_party_costs"] or "",
            row["description"] + (" (expenses)" if row["are_expenses"] else ""),
        )
    table.columns[0].footer = "Total"
    table.columns[4].footer = data["total_cost"]
    table.columns[5].footer = data["total_third_party_costs"]
    console.print(table)
    _echo_more(data, offset, "entries", note="The totals include all of them.")
