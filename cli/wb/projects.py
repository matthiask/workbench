"""Projects"""

import datetime as dt

import click

from wb.core import (
    _bool,
    _complete_short_names,
    _echo_csv,
    _echo_fields,
    _echo_json,
    _echo_more,
    _echo_offer_list,
    _echo_stats,
    _echo_stats_csv,
    _link,
    _page_options,
    _page_params,
    _request,
    _table,
    _terminate,
    _text,
    cli,
    console,
)


@cli.group()
def projects():
    """Find and create projects"""


@projects.command()
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=_complete_short_names)
@click.option("--all", "include_closed", is_flag=True, help="Include closed projects.")
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search(query, customer, owned_by, include_closed, limit, offset, as_csv, as_json):
    """Search projects, open projects by default"""
    params = {"q": " ".join(query), "include_closed": _bool(include_closed)}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = _request("GET", "projects/", params=params | _page_params(limit, offset))
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    table = _table("ID>", "Code", "Title", "Customer", "Owned by", "Closed on")
    for project in data["items"]:
        table.add_row(
            _link(project["id"], project["url"]),
            _link(project["code"], project["url"]),
            project["title"],
            _link(project["customer"]["name"], project["customer"]["url"]),
            project["owned_by"],
            project["closed_on"] or "",
        )
    console.print(table)
    _echo_more(data, offset, "projects")


@projects.command("show")
@click.argument("project_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_project(project_id, as_json):
    """Show a project and its offers"""
    project = _request("GET", f"projects/{project_id}/")
    # Offers require the controlling feature
    offers = _request(
        "GET", "offers/", params={"project": project_id, "limit": 1000}, optional=True
    )
    offers = offers["items"] if offers else None
    if as_json:
        _echo_json(project | {"offers": offers})
        return
    _echo_fields(
        f"{project['code']} {project['title']}",
        [
            ("ID", project["id"]),
            (
                "Customer",
                _link(project["customer"]["name"], project["customer"]["url"]),
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
        _echo_offer_list(offers)


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
    params = {"ids": project_ids, "open": _bool(open_)}
    if closed_since:
        params["closed_since"] = closed_since.date().isoformat()
    data = _request("GET", "projects/stats/", params=params)
    if as_json:
        _echo_json(data)
    elif as_csv:
        _echo_stats_csv(data)
    else:
        _echo_stats(data)


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
    shell_complete=_complete_short_names,
)
@click.option("--description", default="")
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_project(
    title, customer, contact, type_, owned_by, description, dry_run, as_json
):
    """Create a project

    Find the customer and the contact with `wb contacts search`."""
    data = _request(
        "POST",
        "projects/",
        params={"dry_run": _bool(dry_run)},
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
        _echo_json(data)
        return
    _echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", _link(data["customer"]["name"], data["customer"]["url"])),
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
@click.option("--owned-by", help="Short name.", shell_complete=_complete_short_names)
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
        _terminate("Use only one of --close, --closed-on and --reopen.")
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", _text(description)),
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
        _terminate("Nothing to change.")
    data = _request(
        "PATCH",
        f"projects/{project_id}/",
        params={"dry_run": _bool(dry_run)},
        json=data,
    )
    _echo_saved_project(data, dry_run=dry_run, as_json=as_json)
