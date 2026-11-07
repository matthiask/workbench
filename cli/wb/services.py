"""Services"""

import click

from wb.core import (
    cli,
    console,
    echo_csv,
    echo_json,
    echo_more,
    format_bool,
    ignore_warnings_option,
    link,
    load,
    make_table,
    page_options,
    page_params,
    request,
    terminate,
    text_or_stdin,
)


@cli.group()
def services():
    """Look at, create, change, delete and reorder services"""


def _service_options(fn):
    for option in reversed([
        click.option("--title"),
        click.option(
            "--description", help='The text, or - to read it from stdin, "" removes it.'
        ),
        click.option(
            "--external-reference", help='E.g. the URL of an issue, "" removes it.'
        ),
        click.option(
            "--service-type",
            help="Fills in the effort type and the hourly rate unless they are"
            " given too.",
        ),
        click.option("--effort-type"),
        click.option("--hours", type=float),
        click.option("--hourly-rate", type=float),
        click.option("--cost", type=float, help="Fixed costs in addition to hours."),
        click.option(
            "--third-party-costs",
            type=float,
            help="Total incl. tax for third parties contained in the cost.",
        ),
    ]):
        fn = option(fn)
    return fn


def _service_data(file, **values):
    """The service from the YAML or JSON file, the options override it"""
    data = load(file) if file else {}
    if not isinstance(data, dict):
        terminate("The file has to contain a single service.")
    if values.get("description") is not None:
        values["description"] = text_or_stdin(values["description"])
    return data | {key: value for key, value in values.items() if value is not None}


def _echo_service(data, *, dry_run, as_json, prefix=""):
    if as_json:
        echo_json(data)
        return
    if dry_run:
        prefix = "Dry run, nothing changed: " + prefix
    hours = f" | {data['service_hours']}h" if data["service_hours"] else ""
    cost = f" | cost {data['cost']}" if data["cost"] else ""
    console.print(
        f"{prefix}{link(data['id'] or '(new)', data['url'])} {data['title']}"
        f" | offer: {data['offer'] or '(none)'}{hours}{cost}"
        f" | external reference: {data['external_reference'] or '(none)'}"
    )


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


@services.command("create")
@click.argument("file", type=click.File("r"), required=False)
@click.option("--project", type=int, help="Project ID, defaults to the offer's.")
@click.option(
    "--offer",
    type=int,
    help="Offer ID (in preparation or a service group), without offer by default.",
)
@_service_options
@click.option("--optional", is_flag=True, help="Not part of the total.")
@click.option(
    "--after",
    type=int,
    help="ID of the service to add it after, at the end of its offer (or of the"
    " services without offer) by default.",
)
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_service(
    file,
    project,
    offer,
    optional,
    after,
    ignore_warnings,
    dry_run,
    as_json,
    **values,
):
    """Create a service of a project or of an offer

    The service is read from a YAML or JSON file (like a service of `wb offers
    create`) or given with options, which override the file."""
    data = _service_data(
        file,
        **values,
        project=project,
        offer=offer,
        is_optional=optional or None,
        after=after,
    )
    if not data.get("project") and not data.get("offer"):
        terminate("Pass --project or --offer.")
    data = request(
        "POST",
        "services/",
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
        json=data,
    )
    _echo_service(data, dry_run=dry_run, as_json=as_json, prefix="Created ")


@services.command("update")
@click.argument("service_id", type=int)
@click.argument("file", type=click.File("r"), required=False)
@click.option(
    "--offer",
    type=int,
    help="Move the service to this offer of the same project (in preparation"
    " or a service group).",
)
@click.option("--clear-offer", is_flag=True, help="Remove it from its offer.")
@_service_options
@click.option("--optional/--no-optional", default=None, help="Part of the total?")
@click.option("--clear-hours", is_flag=True, help="Remove the hours.")
@click.option("--clear-cost", is_flag=True, help="Remove the cost.")
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_service(
    service_id,
    file,
    offer,
    clear_offer,
    optional,
    clear_hours,
    clear_cost,
    ignore_warnings,
    dry_run,
    as_json,
    **values,
):
    """Change a service or move it to another offer, only the given fields

    Like in the web interface, services of offers which have been sent or
    accepted can't be changed anymore, only their external reference can.
    Logged hours don't prevent changes. The fields can also be read from a
    YAML or JSON file, the options override it."""
    if offer and clear_offer:
        terminate("Pass either --offer or --clear-offer.")
    data = _service_data(file, **values, is_optional=optional)
    if offer or clear_offer:
        data["offer"] = offer
    for flag, field in [(clear_hours, "hours"), (clear_cost, "cost")]:
        if flag and data.get(field) is not None:
            terminate(f"--clear-{field} and --{field} contradict each other.")
        if flag:
            data[field] = None
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"services/{service_id}/",
        json=data,
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
    )
    _echo_service(data, dry_run=dry_run, as_json=as_json)


@services.command("delete")
@click.argument("service_id", type=int)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def delete_service(service_id, dry_run, as_json):
    """Delete a service on which nothing has been logged yet

    Like in the web interface, not when it is bound to an offer which isn't in
    preparation anymore."""
    data = request(
        "DELETE",
        f"services/{service_id}/",
        params={"dry_run": format_bool(dry_run)},
    )
    _echo_service(data, dry_run=dry_run, as_json=as_json, prefix="Deleted ")


@services.command("reorder")
@click.argument("service_ids", type=int, nargs=-1, required=True)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def reorder_services(service_ids, dry_run, as_json):
    """Put the services of an offer, or the services without offer of a
    project, in the given order; all their IDs are required"""
    data = request(
        "POST",
        "services/reorder/",
        params={"dry_run": format_bool(dry_run)},
        json={"services": list(service_ids)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing changed:")
    for service in data:
        console.print(f"{link(service['id'], service['url'])} {service['title']}")


@services.command("reassign-logbook")
@click.argument("service_id", type=int)
@click.option(
    "--to",
    "to",
    type=int,
    required=True,
    help="ID of a service of the same project which allows logging.",
)
@click.option(
    "--include-invoiced",
    is_flag=True,
    help="Also reassign invoiced entries; otherwise they stay with the service"
    " their invoice lines refer to.",
)
@click.option("--dry-run", is_flag=True, help="Validate and count only.")
@click.option("--json", "as_json", is_flag=True)
def reassign_logbook(service_id, to, include_invoiced, dry_run, as_json):
    """Reassign the logged hours and costs of a service to another service,
    like in the web interface (which can also delete the old service)"""
    data = request(
        "POST",
        f"services/{service_id}/reassign-logbook/",
        json={"to": to, "include_invoiced": include_invoiced},
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    prefix = "Dry run, nothing changed: " if dry_run else ""
    source, target = data["from"], data["to"]
    console.print(
        f"{prefix}{data['hours']} logged hours and {data['costs']} logged costs"
        f" from {link(source['id'], source['url'])} {source['title']}"
        f" to {link(target['id'], target['url'])} {target['title']}"
    )
