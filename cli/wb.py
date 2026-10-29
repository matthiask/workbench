import csv
import json
import os
import sys
import tomllib
from pathlib import Path
from urllib.parse import urljoin

import click
import requests
import yaml
from rich import box
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text


CONFIG = Path.home() / ".config" / "workbench.toml"

console = Console(markup=False, highlight=False)


def _terminate(msg):
    click.echo(msg, file=sys.stderr)
    sys.exit(1)


def _config():
    """URL and token from the environment or from the configuration file"""
    config = tomllib.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    url = os.environ.get("WORKBENCH_URL") or config.get("url")
    token = os.environ.get("WORKBENCH_TOKEN") or config.get("token")
    if not url or not token:
        _terminate("Not configured yet. Run `wb login` first.")
    return url, token


def _error(error):
    """A validation error, prefixed with the field if there is one"""
    if loc := ".".join(str(part) for part in error["loc"][2:]):
        return f"{loc}: {error['msg']}"
    return error["msg"]


def _request(method, path, *, optional=False, **kwargs):
    """Request the API, terminate on errors

    ``optional`` requests return ``None`` if access is denied, e.g. because
    a feature is missing."""
    url, token = _config()
    try:
        response = requests.request(
            method,
            urljoin(url, f"/api/{path}"),
            headers={"authorization": f"Bearer {token}"},
            timeout=30,
            **kwargs,
        )
    except requests.RequestException as exc:
        _terminate(str(exc))
    if response.status_code == 403 and optional:
        return None
    if response.status_code == 422:
        _terminate("\n".join(_error(error) for error in response.json()["detail"]))
    if not response.ok:
        try:
            detail = response.json()["detail"]
        except ValueError, KeyError, TypeError:
            detail = response.text
        _terminate(f"{response.status_code}: {detail}")
    return response.json()


class _Loader(yaml.SafeLoader):
    """Keeps dates as strings, the server parses them"""


_Loader.yaml_implicit_resolvers = {
    key: [r for r in resolvers if r[0] != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _load(file):
    """Load data from a YAML or JSON file"""
    try:
        return yaml.load(file, Loader=_Loader)
    except yaml.YAMLError as exc:
        _terminate(f"Invalid YAML or JSON: {exc}")


def _bool(value):
    return "true" if value else "false"


def _echo_json(data):
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _link(text, url):
    """Text which links to the URL in terminals supporting hyperlinks"""
    return Text(str(text), style=Style(link=url)) if url else str(text)


def _table(*columns, **kwargs):
    """A table with headings, columns ending in ">" are right-aligned"""
    table = Table(box=box.SIMPLE_HEAD, **kwargs)
    for column in columns:
        if column.endswith(">"):
            table.add_column(column[:-1], justify="right")
        else:
            table.add_column(column)
    return table


def _echo_fields(title, fields, *, url=None):
    """A bold title followed by the non-empty fields"""
    console.print(_link(title, url), style="bold")
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim")
    grid.add_column()
    for label, value in fields:
        if value:
            grid.add_row(label, str(value))
    console.print(grid)


def _echo_offer(offer):
    _echo_fields(
        f"{offer['code'] or '(new offer)'} {offer['title']}",
        [("ID", offer["id"]), ("Status", offer["status"]), ("URL", offer["url"])],
        url=offer["url"],
    )
    table = _table(
        "Service", "Effort type", "Hours>", "Rate>", "Cost>", show_footer=True
    )
    for service in offer["services"]:
        table.add_row(
            service["title"] + (" (optional)" if service["is_optional"] else ""),
            service["effort_type"],
            service["effort_hours"] or "",
            service["effort_rate"] or "",
            service["service_cost"],
            style="dim" if service["is_optional"] else None,
        )
    table.columns[0].footer = "Subtotal"
    table.columns[-1].footer = offer["subtotal"]
    console.print(table)
    totals = Table.grid(padding=(0, 2))
    totals.add_column()
    totals.add_column(justify="right")
    if float(offer["discount"]):
        totals.add_row("Discount", offer["discount"])
    totals.add_row("Total excl. tax", offer["total_excl_tax"])
    totals.add_row("Total", offer["total"], style="bold")
    console.print(totals)


def _echo_offer_list(offers):
    if not offers:
        console.print("No offers yet.")
        return
    table = _table("ID>", "Code", "Title", "Status", "Total>")
    for offer in offers:
        table.add_row(
            _link(offer["id"], offer["url"]),
            _link(offer["code"], offer["url"]),
            offer["title"],
            offer["status"],
            offer["total"],
        )
    console.print(table)


def _echo_stats(projects):
    table = _table(
        "Code",
        "Title",
        "Closed on",
        "Offered h>",
        "Logged h>",
        "Planned h>",
        "Sold>",
        "Invoiced>",
        "Not invoiced>",
        "Gross margin>",
        "Rate>",
    )
    for stats in projects:
        project = stats["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            project["closed_on"] or "",
            stats["hours"]["offered"],
            stats["hours"]["logged"],
            stats["hours"]["planned"],
            stats["amounts"]["sold"],
            stats["amounts"]["invoiced"],
            stats["amounts"]["not_invoiced"],
            stats["gross_margin"]["gross_margin"],
            stats["gross_margin"]["rate"],
        )
    console.print(table)


def _echo_stats_csv(projects):
    writer = csv.writer(sys.stdout)
    writer.writerow([
        "project_id",
        "project",
        "project_title",
        "closed_on",
        "service_id",
        "service",
        "offer",
        "offer_status",
        "effort_type",
        "effort_rate",
        "is_optional",
        "user",
        "hours",
    ])
    for stats in projects:
        project = stats["project"]
        services = {service["id"]: service for service in stats["services"]}
        for row in stats["logged_hours"]:
            service = services[row["service"]]
            writer.writerow([
                project["id"],
                project["code"],
                project["title"],
                project["closed_on"] or "",
                service["id"],
                service["title"],
                service["offer"] or "",
                service["offer_status"] or "",
                service["effort_type"],
                service["effort_rate"] or "",
                service["is_optional"],
                row["user"],
                row["hours"],
            ])


def _echo_invoice_list(invoices):
    table = _table(
        "ID>",
        "Code",
        "Title",
        "Customer",
        "Status",
        "Invoiced on",
        "Due on",
        "Total excl. tax>",
        title="Invoices",
    )
    for invoice in invoices:
        table.add_row(
            _link(invoice["id"], invoice["url"]),
            _link(invoice["code"], invoice["url"]),
            invoice["title"],
            invoice["customer"],
            invoice["status"],
            invoice["invoiced_on"] or "",
            invoice["due_on"] or "",
            invoice["total_excl_tax"],
        )
    console.print(table)


@click.group()
@click.version_option(package_name="workbench-cli")
def cli():
    pass


@cli.command()
@click.argument("url")
def login(url):
    """Store the Workbench URL and a personal API token

    Create the token in Workbench under "API tokens" in the user menu."""
    token = click.prompt("API token", hide_input=True).strip()
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(f"url = {json.dumps(url)}\ntoken = {json.dumps(token)}\n")
    CONFIG.chmod(0o600)
    click.echo(f"Saved {CONFIG}")


@cli.command()
@click.option("--json", "as_json", is_flag=True)
def whoami(as_json):
    """Show the user and the Workbench installation the token belongs to"""
    data = _request("GET", "me/")
    if as_json:
        _echo_json(data)
        return
    _echo_fields(
        data["full_name"],
        [
            ("Short name", data["short_name"]),
            ("Email", data["email"]),
            ("Workbench", data["url"]),
        ],
        url=data["url"],
    )


@cli.group()
def projects():
    """Find projects"""


@projects.command()
@click.argument("query", nargs=-1)
@click.option("--all", "include_closed", is_flag=True, help="Include closed projects.")
@click.option("--json", "as_json", is_flag=True)
def search(query, include_closed, as_json):
    """Search projects"""
    data = _request(
        "GET",
        "projects/",
        params={"q": " ".join(query), "include_closed": _bool(include_closed)},
    )
    if as_json:
        _echo_json(data)
        return
    table = _table("ID>", "Code", "Title", "Customer", "Owned by", "Closed on")
    for project in data:
        table.add_row(
            _link(project["id"], project["url"]),
            _link(project["code"], project["url"]),
            project["title"],
            project["customer"],
            project["owned_by"],
            project["closed_on"] or "",
        )
    console.print(table)


@projects.command("show")
@click.argument("project_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_project(project_id, as_json):
    """Show a project and its offers"""
    project = _request("GET", f"projects/{project_id}/")
    # Offers require the controlling feature
    offers = _request("GET", f"projects/{project_id}/offers/", optional=True)
    if as_json:
        _echo_json(project | {"offers": offers})
        return
    _echo_fields(
        f"{project['code']} {project['title']}",
        [
            ("ID", project["id"]),
            ("Customer", project["customer"]),
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
@click.option("--customer", type=int, required=True, help="Organization ID.")
@click.option("--contact", type=int, help="Person ID.")
@click.option(
    "--type",
    "type_",
    type=click.Choice(["order", "maintenance", "internal"]),
    default="order",
    show_default=True,
)
@click.option("--owned-by", help="Short name, defaults to you.")
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
    if as_json:
        _echo_json(data)
        return
    _echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", data["customer"]),
            ("Owned by", data["owned_by"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@projects.command()
@click.argument("project_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def invoicing(project_id, as_json):
    """Show the planned invoicing and the invoices of a project"""
    projected = _request("GET", f"projects/{project_id}/projected-invoices/")
    invoices = _request("GET", "invoices/", params={"project": project_id})
    if as_json:
        _echo_json({"projected_invoices": projected, "invoices": invoices})
        return
    table = _table(
        "Invoiced on", "Gross margin>", "Description", title="Planned invoicing"
    )
    for row in projected:
        table.add_row(row["invoiced_on"], row["gross_margin"], row["description"])
    console.print(table)
    _echo_invoice_list(invoices)


@cli.group()
def contacts():
    """Find organizations and people"""


@contacts.command("search")
@click.argument("query", nargs=-1, required=True)
@click.option("--all", "include_archived", is_flag=True, help="Include archived.")
@click.option("--json", "as_json", is_flag=True)
def search_contacts(query, include_archived, as_json):
    """Search organizations and people"""
    params = {"q": " ".join(query), "include_archived": _bool(include_archived)}
    organizations = _request("GET", "contacts/organizations/", params=params)
    people = _request("GET", "contacts/people/", params=params)
    if as_json:
        _echo_json({"organizations": organizations, "people": people})
        return
    table = _table("ID>", "Organization", title="Organizations")
    for organization in organizations:
        table.add_row(
            str(organization["id"]),
            organization["name"]
            + (" (archived)" if organization["is_archived"] else ""),
        )
    console.print(table)
    table = _table("ID>", "Name", "Organization ID>", "Organization", title="People")
    for person in people:
        organization = person["organization"] or {}
        table.add_row(
            str(person["id"]),
            person["full_name"] + (" (archived)" if person["is_archived"] else ""),
            str(organization.get("id", "")),
            organization.get("name", ""),
        )
    console.print(table)


@cli.group()
def offers():
    """Create and update offers"""


@offers.command()
@click.argument("project_id", type=int)
def context(project_id):
    """Print the project, its offers, service types and the offer schema

    Feed this to an LLM together with the specification of the offer."""
    _echo_json(_request("GET", f"projects/{project_id}/offers/context/"))


@offers.command("list")
@click.argument("project_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def list_offers(project_id, as_json):
    """List the offers of a project"""
    data = _request("GET", f"projects/{project_id}/offers/")
    _echo_json(data) if as_json else _echo_offer_list(data)


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
    _echo_json(data) if as_json else _echo_offer(data)


@offers.command()
@click.argument("offer_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def replace(offer_id, file, dry_run, as_json):
    """Replace an offer in preparation and all its services"""
    data = _request(
        "PUT",
        f"offers/{offer_id}/",
        params={"dry_run": _bool(dry_run)},
        json=_load(file),
    )
    _echo_json(data) if as_json else _echo_offer(data)


@cli.group()
def planning():
    """Plan projects: milestones and planned work"""


@planning.command("context")
@click.argument("project_id", type=int)
def planning_context(project_id):
    """Print everything needed to plan a project and the import schema

    Feed this to an LLM together with the plan, e.g. the offer and a timeline."""
    _echo_json(_request("GET", f"projects/{project_id}/planning/context/"))


@planning.command("import")
@click.argument("project_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def planning_import(project_id, file, dry_run, as_json):
    """Add milestones and planned work from a YAML or JSON file"""
    data = _request(
        "POST",
        f"projects/{project_id}/planning/import/",
        params={"dry_run": _bool(dry_run)},
        json=_load(file),
    )
    if as_json:
        _echo_json(data)
        return
    if data["milestones"]:
        table = _table("Milestone", "Date", "Phase starts on", "Estimated hours>")
        for milestone in data["milestones"]:
            table.add_row(
                milestone["title"],
                milestone["date"],
                milestone["phase_starts_on"] or "",
                milestone["estimated_total_hours"],
            )
        console.print(table)
    table = _table(
        "Planned work",
        "User",
        "Service type",
        "Offer",
        "Weeks",
        "Hours>",
        "Provisional",
    )
    for pw in data["planned_work"]:
        weeks = pw["weeks"]
        table.add_row(
            pw["title"],
            pw["user"],
            pw["service_type"],
            pw["offer"] or "",
            f"{weeks[0]} – {weeks[-1]} ({len(weeks)})" if len(weeks) > 1 else weeks[0],
            pw["planned_hours"],
            "yes" if pw["is_provisional"] else "",
        )
    console.print(table)
    for warning in data["warnings"]:
        click.secho(f"Warning: {_error(warning)}", fg="yellow", err=True)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@cli.group()
def invoices():
    """Look at invoices"""


@invoices.command("list")
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option(
    "--status", type=click.Choice(["in_preparation", "sent", "paid", "canceled"])
)
@click.option("--open", "open_", is_flag=True, help="In preparation or sent.")
@click.option("--overdue", is_flag=True, help="Due for more than 15 days.")
@click.option(
    "--since", type=click.DateTime(formats=["%Y-%m-%d"]), help="Invoiced since."
)
@click.option("--json", "as_json", is_flag=True)
def list_invoices(project, customer, status, open_, overdue, since, as_json):
    """List invoices, newest first"""
    params = {"open": _bool(open_), "overdue": _bool(overdue)}
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    if status:
        params["status"] = status
    if since:
        params["invoiced_since"] = since.date().isoformat()
    data = _request("GET", "invoices/", params=params)
    _echo_json(data) if as_json else _echo_invoice_list(data)


@invoices.command("show")
@click.argument("invoice_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_invoice(invoice_id, as_json):
    """Show an invoice"""
    data = _request("GET", f"invoices/{invoice_id}/")
    if as_json:
        _echo_json(data)
        return
    period = (
        f"{data['service_period_from']} – {data['service_period_until']}"
        if data["service_period_from"]
        else None
    )
    _echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Type", data["type"]),
            ("Status", data["status"]),
            ("Customer", data["customer"]),
            ("Owned by", data["owned_by"]),
            ("Invoiced on", data["invoiced_on"]),
            ("Due on", data["due_on"]),
            ("Closed on", data["closed_on"]),
            ("Service period", period),
            ("Total excl. tax", data["total_excl_tax"]),
            ("Third party costs", data["third_party_costs"]),
            ("Total", data["total"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["description"]:
        console.print()
        console.print(data["description"])


@cli.group()
def deals():
    """Look at the sales pipeline"""


@deals.command("list")
@click.argument("query", nargs=-1)
@click.option(
    "--status", type=click.Choice(["open", "accepted", "declined"]), default="open"
)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.")
@click.option("--json", "as_json", is_flag=True)
def list_deals(query, status, customer, owned_by, as_json):
    """List deals, open deals by default"""
    params = {"q": " ".join(query), "status": status}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = _request("GET", "deals/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "ID>",
        "Title",
        "Customer",
        "Owned by",
        "Probability",
        "Decision expected on",
        "Value>",
    )
    for deal in data:
        table.add_row(
            _link(deal["id"], deal["url"]),
            deal["title"],
            deal["customer"],
            deal["owned_by"],
            deal["probability"],
            deal["decision_expected_on"] or "",
            deal["value"],
        )
    console.print(table)


@deals.command("show")
@click.argument("deal_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_deal(deal_id, as_json):
    """Show a deal"""
    data = _request("GET", f"deals/{deal_id}/")
    if as_json:
        _echo_json(data)
        return
    _echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", data["customer"]),
            ("Owned by", data["owned_by"]),
            ("Contributors", ", ".join(data["contributors"])),
            ("Status", data["status"]),
            ("Probability", data["probability"]),
            ("Decision expected on", data["decision_expected_on"]),
            ("Closed on", data["closed_on"]),
            ("Closing type", data["closing_type"]),
            ("Related offers", ", ".join(data["related_offers"])),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    table = _table("Value type", "Value>", show_footer=True)
    for value in data["values"]:
        table.add_row(value["type"], value["value"])
    table.columns[0].footer = "Total"
    table.columns[1].footer = data["value"]
    console.print(table)
    for text in (data["description"], data["closing_notice"]):
        if text:
            console.print(text)


@cli.group()
def reports():
    """Key figures, require the controlling feature (JSON output)"""


@reports.command("key-data")
def key_data():
    """Key data of the last month"""
    _echo_json(_request("GET", "key-data/"))


@reports.command("cash-data")
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Cutoff date, defaults to today.",
)
def cash_data(date):
    """Cash data: Open invoices, planned invoicing, accruals etc."""
    params = {"date": date.date().isoformat()} if date else {}
    _echo_json(_request("GET", "cash-data/", params=params))
