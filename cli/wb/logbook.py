"""Logged hours and costs"""

import click

from wb.core import (
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_json,
    echo_more,
    format_bool,
    link,
    make_table,
    me,
    page_options,
    page_params,
    period_options,
    period_params,
    request,
)


@cli.group(invoke_without_command=True)
@click.pass_context
def hours(ctx):
    """Look at logged hours, log them in Workbench

    Without a command, lists your hours of this week."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_hours, rendered_by=me()["short_name"], period="this-week")


@hours.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.", shell_complete=complete_short_names)
@click.option(
    "--invoiced-hours", is_flag=True, help="Only entries with invoiced hours."
)
@period_options("filters the date the work was done")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_hours(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    invoiced_hours,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search logged hours, newest first

    Invoiced hours (what the work is worth if that is more than the time
    spent) are shown after an arrow."""
    params = {"q": " ".join(query), "invoiced_hours": format_bool(invoiced_hours)}
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    params |= period_params(period, since, until)
    data = request("GET", "logbook/hours/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
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
            link(row["rendered_on"], row["url"]),
            row["rendered_by"],
            link(row["project"]["code"], row["project"]["url"]),
            row["service"],
            row["hours"]
            if row["invoiced_hours"] is None
            else f"{row['hours']} → {row['invoiced_hours']}",
            row["description"],
        )
    table.columns[0].footer = "Total"
    table.columns[4].footer = data["total_hours"]
    console.print(table)
    echo_more(data, offset, "entries", note="The total includes all of them.")


@cli.group()
def costs():
    """Look at logged costs, log them in Workbench"""


@costs.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--expenses", is_flag=True, help="Paid from someone's own pocket.")
@period_options("filters the date the work was done")
@page_options
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
    params = {"q": " ".join(query), "expenses": format_bool(expenses)}
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    params |= period_params(period, since, until)
    data = request("GET", "logbook/costs/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
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
            link(row["rendered_on"], row["url"]),
            row["rendered_by"],
            link(row["project"]["code"], row["project"]["url"]),
            row["service"],
            row["cost"],
            row["third_party_costs"] or "",
            row["description"] + (" (expenses)" if row["are_expenses"] else ""),
        )
    table.columns[0].footer = "Total"
    table.columns[4].footer = data["total_cost"]
    table.columns[5].footer = data["total_third_party_costs"]
    console.print(table)
    echo_more(data, offset, "entries", note="The totals include all of them.")
