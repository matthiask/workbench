"""Projects"""

import datetime as dt

import click

from wb.core import (
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_fields,
    echo_json,
    echo_more,
    echo_offer_list,
    echo_stats,
    echo_stats_csv,
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
def projects():
    """Find and create projects"""


@projects.command()
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--all", "include_closed", is_flag=True, help="Include closed projects.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search(query, customer, owned_by, include_closed, limit, offset, as_csv, as_json):
    """Search projects, open projects by default"""
    params = {"q": " ".join(query), "include_closed": format_bool(include_closed)}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = request("GET", "projects/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Code", "Title", "Customer", "Owned by", "Closed on")
    for project in data["items"]:
        table.add_row(
            link(project["id"], project["url"]),
            link(project["code"], project["url"]),
            project["title"],
            link(project["customer"]["name"], project["customer"]["url"]),
            project["owned_by"],
            project["closed_on"] or "",
        )
    console.print(table)
    echo_more(data, offset, "projects")


@projects.command("show")
@click.argument("project_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_project(project_id, as_json):
    """Show a project and its offers"""
    project = request("GET", f"projects/{project_id}/")
    # Offers require the controlling feature
    offers = request(
        "GET", "offers/", params={"project": project_id, "limit": 1000}, optional=True
    )
    offers = offers["items"] if offers else None
    if as_json:
        echo_json(project | {"offers": offers})
        return
    echo_fields(
        f"{project['code']} {project['title']}",
        [
            ("ID", project["id"]),
            (
                "Customer",
                link(project["customer"]["name"], project["customer"]["url"]),
            ),
            ("Owned by", project["owned_by"]),
            ("Flat rate", project["flat_rate"]),
            ("Closed on", project["closed_on"]),
            ("URL", project["url"]),
        ],
        url=project["url"],
    )
    if project["description"]:
        console.print()
        console.print(project["description"])
    if offers is not None:
        console.print()
        echo_offer_list(offers)


@projects.command()
@click.argument("project_ids", nargs=-1, type=int)
@click.option("--open", "open_", is_flag=True, help="All open projects.")
@click.option(
    "--closed-since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Projects closed on or after this date.",
)
@click.option("--json", "as_json", is_flag=True, help="Everything as JSON.")
@click.option(
    "--csv",
    "as_csv",
    is_flag=True,
    help="Logged hours per project, service and person as CSV.",
)
def stats(project_ids, open_, closed_since, as_json, as_csv):
    """Hours, amounts and gross margins of projects"""
    params = {"ids": project_ids, "open": format_bool(open_)}
    if closed_since:
        params["closed_since"] = closed_since.date().isoformat()
    data = request("GET", "projects/stats/", params=params)
    if as_json:
        echo_json(data)
    elif as_csv:
        echo_stats_csv(data)
    else:
        echo_stats(data)


@projects.command("create")
@click.option("--title", required=True)
@click.option(
    "--customer", type=int, help="Organization ID, defaults to the contact's."
)
@click.option("--contact", type=int, help="Person ID.")
@click.option(
    "--type",
    "type_",
    type=click.Choice(["order", "maintenance", "internal"]),
    default="order",
    show_default=True,
)
@click.option(
    "--owned-by",
    help="Short name, defaults to you.",
    shell_complete=complete_short_names,
)
@click.option("--description", default="")
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_project(
    title, customer, contact, type_, owned_by, description, dry_run, as_json
):
    """Create a project

    Find the customer and the contact with `wb contacts search`."""
    data = request(
        "POST",
        "projects/",
        params={"dry_run": format_bool(dry_run)},
        json={
            "title": title,
            "description": description,
            "customer": customer,
            "contact": contact,
            "type": type_,
            "owned_by": owned_by,
        },
    )
    _echo_saved_project(data, dry_run=dry_run, as_json=as_json)


def _echo_saved_project(data, *, dry_run, as_json):
    if as_json:
        echo_json(data)
        return
    echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", link(data["customer"]["name"], data["customer"]["url"])),
            ("Owned by", data["owned_by"]),
            ("Closed on", data["closed_on"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@projects.command("update")
@click.argument("project_id", type=int)
@click.option("--title")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--contact", type=int, help="Person ID.")
@click.option(
    "--type", "type_", type=click.Choice(["order", "maintenance", "internal"])
)
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--close", is_flag=True, help="Close the project today.")
@click.option(
    "--closed-on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Close the project on this date.",
)
@click.option("--reopen", is_flag=True, help="Open a closed project again.")
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_project(
    project_id,
    title,
    description,
    customer,
    contact,
    type_,
    owned_by,
    close,
    closed_on,
    reopen,
    dry_run,
    as_json,
):
    """Change, close or reopen a project, only the given fields"""
    if sum(map(bool, [close, closed_on, reopen])) > 1:
        terminate("Use only one of --close, --closed-on and --reopen.")
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", text_or_stdin(description)),
            ("customer", customer),
            ("contact", contact),
            ("type", type_),
            ("owned_by", owned_by),
        ]
        if value is not None
    }
    if close:
        data["closed_on"] = dt.date.today().isoformat()
    elif closed_on:
        data["closed_on"] = closed_on.date().isoformat()
    elif reopen:
        data["closed_on"] = None
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"projects/{project_id}/",
        params={"dry_run": format_bool(dry_run)},
        json=data,
    )
    _echo_saved_project(data, dry_run=dry_run, as_json=as_json)
