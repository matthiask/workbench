"""Services"""

import click

from wb.core import (
    cli,
    console,
    echo_csv,
    echo_json,
    echo_more,
    format_bool,
    link,
    make_table,
    page_options,
    page_params,
    request,
    terminate,
    text_or_stdin,
)


@cli.group()
def services():
    """Look at services and the hours and costs logged on them"""


@services.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--external-reference", help="Exact match, e.g. a URL.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_services(
    query, project, offer, external_reference, limit, offset, as_csv, as_json
):
    """Search services, ordered by project and offer"""
    params = {"q": " ".join(query)}
    if project:
        params["project"] = project
    if offer:
        params["offer"] = offer
    if external_reference:
        params["external_reference"] = external_reference
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


@services.command("update")
@click.argument("service_id", type=int)
@click.option(
    "--offer",
    type=int,
    help="Move the service to this offer of the same project (in preparation"
    " or a service group).",
)
@click.option("--clear-offer", is_flag=True, help="Remove it from its offer.")
@click.option(
    "--description", help='The text, or - to read it from stdin, "" removes it.'
)
@click.option("--external-reference", help='E.g. the URL of an issue, "" removes it.')
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_service(
    service_id, offer, clear_offer, description, external_reference, dry_run, as_json
):
    """Move a service to another offer or change its description or external
    reference

    Like in the web interface, services of offers which have been sent or
    accepted can't be moved and their description can't be changed, but their
    external reference can.
    Other fields are changed with `wb offers services update`."""
    if offer and clear_offer:
        terminate("Pass either --offer or --clear-offer.")
    data = {}
    if offer or clear_offer:
        data["offer"] = offer
    if description is not None:
        data["description"] = text_or_stdin(description)
    if external_reference is not None:
        data["external_reference"] = external_reference
    if not data:
        terminate(
            "Nothing to change, pass --offer, --clear-offer, --description or"
            " --external-reference."
        )
    data = request(
        "PATCH",
        f"services/{service_id}/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    prefix = "Dry run, nothing changed: " if dry_run else ""
    console.print(
        f"{prefix}{link(data['id'], data['url'])} {data['title']}"
        f" | offer: {data['offer'] or '(none)'}"
        f" | external reference: {data['external_reference'] or '(none)'}"
    )
