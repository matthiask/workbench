"""Services"""

import click

from wb.core import (
    cli,
    console,
    echo_csv,
    echo_json,
    echo_more,
    link,
    make_table,
    page_options,
    page_params,
    request,
)


@cli.group()
def services():
    """Look at services and the hours and costs logged on them"""


@services.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--offer", type=int, help="Offer ID.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_services(query, project, offer, limit, offset, as_csv, as_json):
    """Search services, ordered by project and offer"""
    params = {"q": " ".join(query)}
    if project:
        params["project"] = project
    if offer:
        params["offer"] = offer
    data = request("GET", "services/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
        "ID>",
        "Project",
        "Offer",
        "Service",
        "Effort type",
        "Logged h>",
        "Hours>",
        "Logged cost>",
        "Cost>",
    )
    for service in data["items"]:
        notes = [
            note
            for note, flag in [
                ("optional", service["is_optional"]),
                ("no logging", not service["is_logging_allowed"]),
            ]
            if flag
        ]
        table.add_row(
            link(service["id"], service["url"]),
            link(service["project"]["code"], service["project"]["url"]),
            service["offer"] or "",
            service["title"] + (f" ({', '.join(notes)})" if notes else ""),
            service["effort_type"],
            service["logged_hours"],
            service["service_hours"],
            service["logged_cost"],
            service["cost"] or "",
            style="dim" if notes else None,
        )
    console.print(table)
    echo_more(data, offset, "services")
