"""Offers and their services"""

import click

from wb.core import (
    _bool,
    _complete_short_names,
    _echo_csv,
    _echo_json,
    _echo_more,
    _echo_offer,
    _echo_offer_list,
    _error,
    _load,
    _page_options,
    _page_params,
    _period_options,
    _period_params,
    _request,
    _terminate,
    _text,
    cli,
)


@cli.group()
def offers():
    """Create and update offers"""


@offers.command()
@click.argument("project_id", type=int)
def context(project_id):
    """Print the project, its offers, service types and the offer schema

    Feed this to an LLM together with the specification of the offer."""
    _echo_json(_request("GET", f"projects/{project_id}/offers/context/"))


@offers.command("search")
@click.argument("query", nargs=-1)
@click.option(
    "--status",
    type=click.Choice([
        "in_preparation",
        "service_group",
        "offered",
        "accepted",
        "declined",
    ]),
)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=_complete_short_names)
@_period_options("filters the offer date")
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_offers(
    query,
    status,
    project,
    customer,
    owned_by,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search offers, newest first"""
    params = {"q": " ".join(query)}
    if status:
        params["status"] = status
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    params |= _period_params(period, since, until)
    data = _request("GET", "offers/", params=params | _page_params(limit, offset))
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    _echo_offer_list(data["items"])
    _echo_more(data, offset, "offers")


@offers.command()
@click.argument("offer_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show(offer_id, as_json):
    """Show an offer"""
    data = _request("GET", f"offers/{offer_id}/")
    _echo_json(data) if as_json else _echo_offer(data)


@offers.command()
@click.argument("project_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def create(project_id, file, dry_run, as_json):
    """Create an offer in preparation from a YAML or JSON file"""
    data = _request(
        "POST",
        f"projects/{project_id}/offers/",
        params={"dry_run": _bool(dry_run)},
        json=_load(file),
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)


@offers.command()
@click.argument("offer_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def replace(offer_id, file, dry_run, as_json):
    """Replace an offer in preparation and all its services

    Use this for a new version of the whole offer; `wb offers update` and
    `wb offers services` change parts of it."""
    data = _request(
        "PUT",
        f"offers/{offer_id}/",
        params={"dry_run": _bool(dry_run)},
        json=_load(file),
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)


def _echo_changed_offer(data, *, dry_run, as_json):
    if as_json:
        _echo_json(data)
        return
    _echo_offer(data)
    for warning in data["warnings"]:
        click.secho(f"Warning: {_error(warning)}", fg="yellow", err=True)
    if dry_run:
        click.secho("Dry run, nothing has been saved.", fg="yellow", err=True)


@offers.command("update")
@click.argument("offer_id", type=int)
@click.option("--title")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option(
    "--discount", type=float, help="Amount excl. tax, 0 removes the discount."
)
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def update_offer(offer_id, title, description, discount, dry_run, as_json):
    """Change the title, the description or the discount of an offer in
    preparation"""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", _text(description)),
            ("discount", discount),
        ]
        if value is not None
    }
    if not data:
        _terminate("Nothing to change, pass --title, --description or --discount.")
    data = _request(
        "PATCH",
        f"offers/{offer_id}/",
        params={"dry_run": _bool(dry_run)},
        json=data,
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)


@offers.group("services")
def offer_services():
    """Add, change, delete and reorder services of offers in preparation"""


def _service_options(fn):
    for option in reversed([
        click.option("--title"),
        click.option("--description", help="The text, or - to read it from stdin."),
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
    data = _load(file) if file else {}
    if not isinstance(data, dict):
        _terminate("The file has to contain a single service.")
    if values.get("description") is not None:
        values["description"] = _text(values["description"])
    return data | {key: value for key, value in values.items() if value is not None}


@offer_services.command("add")
@click.argument("offer_id", type=int)
@click.argument("file", type=click.File("r"), required=False)
@_service_options
@click.option("--optional", is_flag=True, help="Not part of the total.")
@click.option("--after", type=int, help="ID of the service to add it after.")
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def add_service(offer_id, file, optional, after, dry_run, as_json, **values):
    """Add a service, at the end by default

    The service is read from a YAML or JSON file (like a service of `wb offers
    create`) or given with options, which override the file."""
    data = _service_data(file, **values, is_optional=optional or None, after=after)
    data = _request(
        "POST",
        f"offers/{offer_id}/services/",
        params={"dry_run": _bool(dry_run)},
        json=data,
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)


@offer_services.command("update")
@click.argument("offer_id", type=int)
@click.argument("service_id", type=int)
@click.argument("file", type=click.File("r"), required=False)
@_service_options
@click.option("--optional/--no-optional", default=None, help="Part of the total?")
@click.option("--clear-hours", is_flag=True, help="Remove the hours.")
@click.option("--clear-cost", is_flag=True, help="Remove the cost.")
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def update_service(
    offer_id,
    service_id,
    file,
    optional,
    clear_hours,
    clear_cost,
    dry_run,
    as_json,
    **values,
):
    """Change a service, only the given fields

    Logged hours don't prevent changes, like in the web interface."""
    data = _service_data(file, **values, is_optional=optional)
    for flag, field in [(clear_hours, "hours"), (clear_cost, "cost")]:
        if flag and data.get(field) is not None:
            _terminate(f"--clear-{field} and --{field} contradict each other.")
        if flag:
            data[field] = None
    if not data:
        _terminate("Nothing to change.")
    data = _request(
        "PATCH",
        f"offers/{offer_id}/services/{service_id}/",
        params={"dry_run": _bool(dry_run)},
        json=data,
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)


@offer_services.command("delete")
@click.argument("offer_id", type=int)
@click.argument("service_id", type=int)
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def delete_service(offer_id, service_id, dry_run, as_json):
    """Delete a service on which nothing has been logged yet"""
    data = _request(
        "DELETE",
        f"offers/{offer_id}/services/{service_id}/",
        params={"dry_run": _bool(dry_run)},
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)


@offer_services.command("reorder")
@click.argument("offer_id", type=int)
@click.argument("service_ids", type=int, nargs=-1, required=True)
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def reorder_services(offer_id, service_ids, dry_run, as_json):
    """Put the services in the given order, all their IDs are required"""
    data = _request(
        "POST",
        f"offers/{offer_id}/services/reorder/",
        params={"dry_run": _bool(dry_run)},
        json={"services": list(service_ids)},
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)
