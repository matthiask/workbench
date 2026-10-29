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
from rich.table import Table


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


def _request(method, path, **kwargs):
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
    if response.status_code == 422:
        errors = response.json()["detail"]
        _terminate(
            "\n".join(
                f"{'.'.join(str(part) for part in error['loc'][2:])}: {error['msg']}"
                for error in errors
            )
        )
    if not response.ok:
        try:
            detail = response.json()["detail"]
        except ValueError, KeyError, TypeError:
            detail = response.text
        _terminate(f"{response.status_code}: {detail}")
    return response.json()


def _load(file):
    """Load an offer from a YAML or JSON file"""
    try:
        return yaml.safe_load(file)
    except yaml.YAMLError as exc:
        _terminate(f"Invalid YAML or JSON: {exc}")


def _bool(value):
    return "true" if value else "false"


def _echo_json(data):
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _table(*columns, **kwargs):
    """A table with headings, columns ending in ">" are right-aligned"""
    table = Table(box=box.SIMPLE_HEAD, **kwargs)
    for column in columns:
        if column.endswith(">"):
            table.add_column(column[:-1], justify="right")
        else:
            table.add_column(column)
    return table


def _echo_fields(title, fields):
    """A bold title followed by the non-empty fields"""
    console.print(title, style="bold")
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
            str(offer["id"]),
            offer["code"],
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
            project["code"],
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
            str(project["id"]),
            project["code"],
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
    offers = _request("GET", f"projects/{project_id}/offers/")
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
    )
    if project["description"]:
        console.print()
        console.print(project["description"])
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
