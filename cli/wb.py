import json
import os
import sys
import tomllib
from pathlib import Path
from urllib.parse import urljoin

import click
import requests
import yaml


CONFIG = Path.home() / ".config" / "workbench.toml"


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


def _echo_offer(offer):
    click.secho(f"{offer['code'] or '(new offer)'} {offer['title']}", bold=True)
    if offer["id"]:
        click.echo(f"ID: {offer['id']}")
    click.echo(f"Status: {offer['status']}")
    if offer["url"]:
        click.echo(offer["url"])
    click.echo()
    for service in offer["services"]:
        effort = (
            f"{service['effort_hours']}h {service['effort_type']}"
            f" à {service['effort_rate']}"
            if service["effort_hours"]
            else ""
        )
        optional = " (optional)" if service["is_optional"] else ""
        click.echo(
            f"{service['service_cost']:>12}  {service['title']}{optional}"
            + (f"  [{effort}]" if effort else "")
        )
    click.echo()
    click.echo(f"{offer['subtotal']:>12}  Subtotal")
    if float(offer["discount"]):
        click.echo(f"{offer['discount']:>12}  Discount")
    click.echo(f"{offer['total']:>12}  Total")


def _echo_offer_list(offers):
    if not offers:
        click.echo("No offers yet.")
    for offer in offers:
        click.echo(
            f"{offer['id']:>6}  {offer['code']}  {offer['total']:>12}"
            f"  {offer['title']} ({offer['status']})"
        )


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
    for project in data:
        closed = f" (closed {project['closed_on']})" if project["closed_on"] else ""
        click.echo(
            f"{project['id']:>6}  {project['code']}  {project['title']}"
            f" - {project['customer']}{closed}"
        )


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
    click.secho(f"{project['code']} {project['title']}", bold=True)
    click.echo(f"ID: {project['id']}")
    click.echo(f"Customer: {project['customer']}")
    click.echo(f"Owned by: {project['owned_by']}")
    if project["flat_rate"]:
        click.echo(f"Flat rate: {project['flat_rate']}")
    if project["closed_on"]:
        click.echo(f"Closed on: {project['closed_on']}")
    click.echo(project["url"])
    if project["description"]:
        click.echo()
        click.echo(project["description"])
    click.echo()
    _echo_offer_list(offers)


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
