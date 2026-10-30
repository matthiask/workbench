import csv
import datetime as dt
import json
import os
import platform
import re
import secrets
import shlex
import socket
import sys
import threading
import time
import tomllib
import traceback
import webbrowser
from functools import cache
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.metadata import version
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import click
import requests
import yaml
from click.shell_completion import (
    BashComplete,
    CompletionItem,
    FishComplete,
    ZshComplete,
    add_completion_class,
    get_completion_class,
)
from rich import box
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text


CONFIG = Path.home() / ".config" / "workbench.toml"
BUG_REPORTS = Path.home() / ".cache" / "wb"


def _version():
    """The version of the checkout for editable installs, their metadata
    keeps the version they were installed with"""
    pyproject = Path(__file__).with_name("pyproject.toml")
    if pyproject.exists():
        return tomllib.loads(pyproject.read_text())["project"]["version"]
    return version("workbench-cli")


VERSION = _version()

console = Console(markup=False, highlight=False)


def _terminate(msg):
    click.echo(msg, file=sys.stderr)
    sys.exit(1)


class _ServerError(Exception):
    """Workbench failed, the bug report contains the request and the response"""

    def __init__(self, status_code, details):
        super().__init__(status_code)
        self.status_code = status_code
        self.details = details


def _bug_report(problem, details, *, args):
    """Write what's needed to fix a bug into a file people can send"""
    try:
        url = _url(os.environ.get("WORKBENCH_URL")) or _read_config()["current"]
    except Exception:  # noqa: BLE001
        url = None
    now = dt.datetime.now().astimezone()
    report = "\n".join([
        f"wb {VERSION}, Python {platform.python_version()} on {platform.platform()}",
        f"Installation: {url or 'unknown'}",
        f"Command: {shlex.join(['wb', *args])}",
        f"Time: {now.isoformat(timespec='seconds')}",
        "",
        details,
    ])
    path = BUG_REPORTS / f"bug-report-{now:%Y%m%d-%H%M%S}.txt"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report)
    except OSError:
        _terminate(
            f"{problem} Please send this to the people running Workbench:\n\n{report}"
        )
    _terminate(
        f"{problem} Please send {path} to the people running Workbench"
        " and tell them what you tried to do."
    )


class _Group(click.Group):
    """Commands which crash write a bug report instead of a traceback, set
    WB_DEBUG to get the exception"""

    def main(self, args=None, **kwargs):
        args = sys.argv[1:] if args is None else list(args)
        try:
            return super().main(args, **kwargs)
        except Exception as exc:
            if os.environ.get("WB_DEBUG"):
                raise
            if isinstance(exc, _ServerError):
                _bug_report(
                    f"Workbench failed ({exc.status_code}).", exc.details, args=args
                )
            _bug_report(
                f"wb crashed ({type(exc).__name__}: {exc}).",
                traceback.format_exc(),
                args=args,
            )


def _read_config():
    """The current installation's URL and the tokens of all installations

    Older versions stored the URL and the token of a single installation."""
    config = tomllib.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    if "url" in config:
        config = {
            "current": config["url"],
            "installations": {config["url"]: {"token": config.get("token", "")}},
        }
    # Older versions stored URLs as given. Entries which are normalized
    # already come from newer versions and take precedence.
    installations = {}
    for url, installation in sorted(
        config.get("installations", {}).items(),
        key=lambda item: item[0] == _url(item[0]),
    ):
        installations[_url(url)] = installation
    return {"current": _url(config.get("current")), "installations": installations}


def _url(url):
    """The scheme and the host which identify an installation, URLs may be
    pasted from the browser"""
    if not url:
        return url
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc.lower()}"


def _write_config(config):
    lines = [f"current = {json.dumps(config['current'])}"]
    for url, installation in sorted(config["installations"].items()):
        lines += [
            "",
            f"[installations.{json.dumps(url)}]",
            f"token = {json.dumps(installation['token'])}",
        ]
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text("\n".join(lines) + "\n")
    CONFIG.chmod(0o600)


def _save_config(url, token):
    """Store the token of the installation and make it the current one"""
    config = _read_config()
    config["installations"][url] = {"token": token}
    config["current"] = url
    _write_config(config)


def _config():
    """URL and token from the environment or from the configuration file

    WORKBENCH_URL alone selects one of the installations wb is logged in to."""
    config = _read_config()
    url = _url(os.environ.get("WORKBENCH_URL")) or config["current"]
    token = os.environ.get("WORKBENCH_TOKEN") or (
        config["installations"].get(url, {}).get("token")
    )
    if not url or not token:
        _terminate("Not configured yet. Run `wb login URL` first.")
    return url, token


def _can_login_again():
    """Expired tokens are replaced through the browser, but only for people
    sitting in front of a terminal, and only if the token is stored by wb"""
    return sys.stdin.isatty() and not os.environ.get("WORKBENCH_TOKEN")


LOGIN_TIMEOUT = 300


def _browser_login(url):
    """Authorize wb in the browser and store the token

    Workbench posts the token to a server listening on a local port, the
    state protects against tokens posted by others."""
    state = secrets.token_urlsafe(24)
    result = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("content-length", 0))
            data = parse_qs(self.rfile.read(length).decode())
            if data.get("state") != [state] or not data.get("token"):
                self.send_error(400)
                return
            result["token"] = data["token"][0]
            body = b"wb is authorized. You can close this window."
            self.send_response(200)
            self.send_header("content-type", "text/plain; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 1
    login_url = (
        urljoin(url, "/cli-login/")
        + "?"
        + urlencode({
            "port": server.server_address[1],
            "state": state,
            "name": socket.gethostname(),
        })
    )
    click.echo(f"Authorize wb in your browser: {login_url}", err=True)
    # webbrowser waits for some browser commands to exit, serve meanwhile
    threading.Thread(target=webbrowser.open, args=[login_url], daemon=True).start()
    deadline = time.monotonic() + LOGIN_TIMEOUT
    with server:
        while "token" not in result and time.monotonic() < deadline:
            server.handle_request()
    if "token" not in result:
        _terminate("Timed out waiting for the browser.")
    _save_config(url, result["token"])
    click.echo(f"Saved {CONFIG}", err=True)
    return result["token"]


def _parse_version(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return ()


@cache
def _check_version(latest):
    """Tell the user about a newer version, once"""
    if latest and _parse_version(latest) > _parse_version(VERSION):
        click.secho(
            f"wb {latest} is available (you have {VERSION}):"
            " uv tool upgrade workbench-cli",
            fg="yellow",
            err=True,
        )


def _error(error):
    """A validation error, prefixed with the field if there is one"""
    if loc := ".".join(str(part) for part in error["loc"][2:]):
        return f"{loc}: {error['msg']}"
    return error["msg"]


def _send(method, url, path, token, **kwargs):
    try:
        return requests.request(
            method,
            urljoin(url, f"/api/{path}"),
            headers={"authorization": f"Bearer {token}", "x-workbench-cli": VERSION},
            timeout=30,
            **kwargs,
        )
    except requests.RequestException as exc:
        _terminate(str(exc))


def _request(method, path, *, optional=False, **kwargs):
    """Request the API, terminate on errors

    ``optional`` requests return ``None`` if access is denied, e.g. because
    a feature is missing. Expired tokens are replaced and the request is
    sent again."""
    url, token = _config()
    response = _send(method, url, path, token, **kwargs)
    if response.status_code == 401 and _can_login_again():
        click.secho("Your access has expired.", fg="yellow", err=True)
        token = _browser_login(url)
        response = _send(method, url, path, token, **kwargs)
    _check_version(response.headers.get("x-workbench-cli-latest"))
    if response.status_code == 401:
        _terminate("Not authorized (anymore). Run `wb login` to log in again.")
    if response.status_code == 403 and optional:
        return None
    if response.status_code == 422:
        _terminate("\n".join(_error(error) for error in response.json()["detail"]))
    if response.status_code >= 500:
        raise _ServerError(
            response.status_code,
            f"{method} {path} {kwargs.get('params') or ''}\n"
            f"{response.status_code} {response.headers.get('date', '')}\n\n"
            f"{response.text[:2000]}",
        )
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
            grid.add_row(label, value if isinstance(value, Text) else str(value))
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
            _link(invoice["customer"]["name"], invoice["customer"]["url"]),
            invoice["status"],
            invoice["invoiced_on"] or "",
            invoice["due_on"] or "",
            invoice["total_excl_tax"],
        )
    console.print(table)


@click.group(cls=_Group)
@click.version_option(VERSION)
def cli():
    pass


@cli.command()
@click.argument("url", required=False)
@click.option(
    "--token",
    "paste_token",
    is_flag=True,
    help="Paste a token from the API tokens page instead of using the browser.",
)
def login(url, paste_token):
    """Authorize wb to access Workbench in your name

    Opens the browser; the URL defaults to the current installation. Logging
    in to another installation adds it and makes it the current one (see `wb
    auth`). Use --token on computers without a browser."""
    if not (url := url or _read_config()["current"]):
        _terminate("Which Workbench? Run `wb login URL`.")
    url = _url(url)
    if paste_token:
        _save_config(url, click.prompt("API token", hide_input=True).strip())
        click.echo(f"Saved {CONFIG}")
    else:
        _browser_login(url)


class _CompleteOptions:
    """Offer the options when there's nothing else to complete, Click only
    does this when a dash has been typed"""

    def get_completions(self, args, incomplete):
        completions = super().get_completions(args, incomplete)
        # After an option its value may be expected, e.g. an ID
        if not (completions or incomplete or (args and args[-1].startswith("-"))):
            completions = super().get_completions(args, "-")
        return completions


for _shell, _class in [
    ("bash", BashComplete),
    ("zsh", ZshComplete),
    ("fish", FishComplete),
]:
    add_completion_class(type(_class.__name__, (_CompleteOptions, _class), {}), _shell)


@cli.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell):
    """Print the script which completes wb's commands in your shell

    bash: echo 'eval "$(wb completion bash)"' >> ~/.bashrc

    zsh: echo 'eval "$(wb completion zsh)"' >> ~/.zshrc

    fish: wb completion fish > ~/.config/fish/completions/wb.fish"""
    complete = get_completion_class(shell)(cli, {}, "wb", "_WB_COMPLETE")
    click.echo(complete.source())


@cli.group()
def auth():
    """Switch between the Workbench installations you're logged in to

    `wb login URL` adds installations. Setting WORKBENCH_URL uses another
    installation for a single command."""


@auth.command("list")
def list_installations():
    """List the installations, the current one is marked with *"""
    config = _read_config()
    if not config["installations"]:
        _terminate("Not configured yet. Run `wb login URL` first.")
    for url in sorted(config["installations"]):
        click.echo(f"{'*' if url == config['current'] else ' '} {url}")


def _complete_installations(ctx, param, incomplete):
    # Host names only: bash splits words at the colon of https://
    return [
        CompletionItem(host)
        for host in sorted(
            urlsplit(url).netloc for url in _read_config()["installations"]
        )
        if incomplete in host
    ]


@auth.command("switch")
@click.argument("name", shell_complete=_complete_installations)
def switch_installation(name):
    """Use another installation, NAME is any unique part of its URL"""
    config = _read_config()
    urls = sorted(config["installations"])
    matches = [url for url in urls if url == name] or [
        url for url in urls if name in url
    ]
    if len(matches) != 1:
        _terminate(
            f"{'Several' if matches else 'No'} installations match {name!r}:"
            f" {', '.join(matches or urls) or '(none)'}. Add new ones with"
            " `wb login URL`."
        )
    config["current"] = matches[0]
    _write_config(config)
    click.echo(f"Using {matches[0]}")


@cli.command()
@click.option("--json", "as_json", is_flag=True)
def me(as_json):
    """Who you are and what's on your plate: projects, this week's planning,
    offers, invoices and deals which may need action"""
    user = _request("GET", "me/")
    data = _request("GET", "me/overview/")
    if as_json:
        _echo_json({"user": user} | data)
        return

    _echo_fields(
        user["full_name"],
        [
            ("Short name", user["short_name"]),
            ("Email", user["email"]),
            ("Workbench", user["url"]),
        ],
        url=user["url"],
    )
    table = _table("ID>", "Code", "Title", "Customer", title="Your open projects")
    for project in data["projects"]:
        table.add_row(
            _link(project["id"], project["url"]),
            _link(project["code"], project["url"]),
            project["title"],
            _link(project["customer"]["name"], project["customer"]["url"]),
        )
    console.print(table)

    table = _table(
        "Project",
        "Planned work",
        "Hours>",
        "Provisional",
        title=f"Week of {data['week']}",
    )
    for pw in data["planned_work"]:
        project = pw["project"]
        table.add_row(
            _link(f"{project['code']} {project['title']}", project["url"]),
            pw["title"],
            pw["hours"],
            "yes" if pw["is_provisional"] else "",
        )
    console.print(table)

    if data["offers"] is not None:
        table = _table("ID>", "Code", "Title", "Status", "Total>", title="Offers")
        for offer in data["offers"]:
            table.add_row(
                _link(offer["id"], offer["url"]),
                _link(offer["code"], offer["url"]),
                offer["title"],
                offer["status"],
                offer["total"],
            )
        console.print(table)
    if data["invoices"] is not None:
        _echo_invoice_list(data["invoices"])
    if data["deals"] is not None:
        table = _table(
            "ID>", "Title", "Customer", "Decision expected on", "Value>", title="Deals"
        )
        for deal in data["deals"]:
            table.add_row(
                _link(deal["id"], deal["url"]),
                deal["title"],
                _link(deal["customer"]["name"], deal["customer"]["url"]),
                deal["decision_expected_on"] or "",
                deal["value"],
            )
        console.print(table)


@cli.group()
def users():
    """Find users and their short names"""


@users.command("search")
@click.argument("query", nargs=-1)
@click.option("--all", "include_inactive", is_flag=True, help="Include inactive.")
@click.option("--json", "as_json", is_flag=True)
def search_users(query, include_inactive, as_json):
    """Search users by name, short name or email address, active users by
    default"""
    params = {"q": " ".join(query), "include_inactive": _bool(include_inactive)}
    data = _request("GET", "users/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table("ID>", "Short name", "Name", "Email", "Teams")
    for user in data:
        table.add_row(
            _link(user["id"], user["url"]),
            user["short_name"],
            _link(user["full_name"], user["url"])
            + ("" if user["is_active"] else " (inactive)"),
            user["email"],
            ", ".join(user["teams"]),
        )
    console.print(table)


@cli.group()
def projects():
    """Find and create projects"""


@projects.command()
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.")
@click.option("--all", "include_closed", is_flag=True, help="Include closed projects.")
@click.option("--json", "as_json", is_flag=True)
def search(query, customer, owned_by, include_closed, as_json):
    """Search projects, open projects by default"""
    params = {"q": " ".join(query), "include_closed": _bool(include_closed)}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = _request("GET", "projects/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table("ID>", "Code", "Title", "Customer", "Owned by", "Closed on")
    for project in data:
        table.add_row(
            _link(project["id"], project["url"]),
            _link(project["code"], project["url"]),
            project["title"],
            _link(project["customer"]["name"], project["customer"]["url"]),
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
            ("Customer", _link(data["customer"]["name"], data["customer"]["url"])),
            ("Owned by", data["owned_by"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@cli.group()
def contacts():
    """Search organizations and people"""


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
        url = organization["url"]
        table.add_row(
            _link(organization["id"], url),
            _link(organization["name"], url)
            + (" (archived)" if organization["is_archived"] else ""),
        )
    console.print(table)
    table = _table("ID>", "Name", "Organization ID>", "Organization", title="People")
    for person in people:
        organization = person["organization"] or {}
        table.add_row(
            _link(person["id"], person["url"]),
            _link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
            _link(organization.get("id", ""), organization.get("url")),
            _link(organization.get("name", ""), organization.get("url")),
        )
    console.print(table)


@cli.group()
def organizations():
    """Look at organizations, search them with `wb contacts search`"""


@organizations.command("show")
@click.argument("organization_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_organization(organization_id, as_json):
    """Show an organization and its people"""
    data = _request("GET", f"contacts/organizations/{organization_id}/")
    if as_json:
        _echo_json(data)
        return
    _echo_fields(
        data["name"] + (" (archived)" if data["is_archived"] else ""),
        [
            ("ID", data["id"]),
            ("Primary contact", data["primary_contact"]),
            ("Groups", ", ".join(data["groups"])),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["notes"]:
        console.print()
        console.print(data["notes"])
    table = _table("ID>", "Name", title="People")
    for person in data["people"]:
        table.add_row(
            _link(person["id"], person["url"]),
            _link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
        )
    console.print(table)


@cli.group()
def people():
    """Look at and add people, search them with `wb contacts search`"""


@people.command("show")
@click.argument("person_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_person(person_id, as_json):
    """Show a person and their contact details"""
    data = _request("GET", f"contacts/people/{person_id}/")
    _echo_json(data) if as_json else _echo_person(data)


@people.command("context")
def people_context():
    """Print the schema of a person to create

    Feed this to an LLM together with an email signature, a business card
    or whatever you've got."""
    _echo_json(_request("GET", "contacts/people/context/"))


@people.command("create")
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option(
    "--allow-duplicates",
    is_flag=True,
    help="Create the person (and the organization) even if the name exists already.",
)
@click.option("--json", "as_json", is_flag=True)
def create_person(file, dry_run, allow_duplicates, as_json):
    """Create a person with their contact details from a YAML or JSON file

    Search for the person and their organization with `wb contacts search`
    first. Email addresses which are already in use are always rejected."""
    data = _request(
        "POST",
        "contacts/people/",
        params={
            "dry_run": _bool(dry_run),
            "allow_duplicates": _bool(allow_duplicates),
        },
        json=_load(file),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_person(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@people.command("add-details")
@click.argument("person_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def add_person_details(person_id, file, dry_run, as_json):
    """Add email addresses, phone numbers and postal addresses to a person

    The YAML or JSON file contains email_addresses, phone_numbers and
    postal_addresses like for `wb people create`. Existing details are never
    changed or removed."""
    data = _request(
        "POST",
        f"contacts/people/{person_id}/details/",
        params={"dry_run": _bool(dry_run)},
        json=_load(file),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_person(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


def _echo_person(data):
    organization = data["organization"] or {}
    _echo_fields(
        data["full_name"] + (" (archived)" if data["is_archived"] else ""),
        [
            ("ID", data["id"]),
            (
                "Organization",
                _link(organization.get("name", ""), organization.get("url")),
            ),
            ("Organization ID", organization.get("id")),
            ("Salutation", data["salutation"]),
            ("Primary contact", data["primary_contact"]),
            ("Groups", ", ".join(data["groups"])),
            *(
                (f"{label} ({detail['type']})", detail["value"])
                for label, key in [
                    ("Email", "email_addresses"),
                    ("Phone", "phone_numbers"),
                    ("Address", "postal_addresses"),
                ]
                for detail in data[key]
            ),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["notes"]:
        console.print()
        console.print(data["notes"])


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
@click.option("--owned-by", help="Short name.")
@click.option("--json", "as_json", is_flag=True)
def search_offers(query, status, project, customer, owned_by, as_json):
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
    data = _request("GET", "offers/", params=params)
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


@invoices.command("search")
@click.argument("query", nargs=-1)
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
def search_invoices(query, project, customer, status, open_, overdue, since, as_json):
    """Search invoices, newest first"""
    params = {"q": " ".join(query), "open": _bool(open_), "overdue": _bool(overdue)}
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
            ("Customer", _link(data["customer"]["name"], data["customer"]["url"])),
            (
                "Project",
                _link(f"{project['code']} {project['title']}", project["url"])
                if (project := data["project"])
                else None,
            ),
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
def notes():
    """Search and add notes on deals and invoices"""


def _echo_notes(notes):
    for note in notes:
        obj = note["object"]
        console.print(
            _link(f"{obj['name']} ({obj['type']} {obj['id']})", obj["url"]),
            style="bold",
        )
        console.print(
            f"{note['title']} – {note['created_by']}, {note['created_at'][:10]}",
            style="dim",
        )
        console.print(note["description"])
        console.print()


@notes.command("search")
@click.argument("query", nargs=-1)
@click.option("--deal", type=int, help="Deal ID.")
@click.option("--invoice", type=int, help="Invoice ID.")
@click.option("--recurring-invoice", type=int, help="Recurring invoice ID.")
@click.option("--created-by", help="Short name.")
@click.option("--json", "as_json", is_flag=True)
def search_notes(query, deal, invoice, recurring_invoice, created_by, as_json):
    """Search notes, all of them or those of some objects, newest first"""
    params = {"q": " ".join(query)}
    for key, value in [
        ("deal", deal),
        ("invoice", invoice),
        ("recurring_invoice", recurring_invoice),
        ("created_by", created_by),
    ]:
        if value:
            params[key] = value
    data = _request("GET", "notes/", params=params)
    if as_json:
        _echo_json(data)
    elif data:
        _echo_notes(data)
    else:
        console.print("No notes found.")


@notes.command("create")
@click.option("--deal", type=int, help="Deal ID.")
@click.option("--invoice", type=int, help="Invoice ID.")
@click.option("--recurring-invoice", type=int, help="Recurring invoice ID.")
@click.option("--title", required=True)
@click.option("--description", required=True)
@click.option("--json", "as_json", is_flag=True)
def create_note(deal, invoice, recurring_invoice, title, description, as_json):
    """Add a note to exactly one deal, invoice or recurring invoice

    Like in Workbench, the owner of the deal or invoice is notified by email."""
    data = _request(
        "POST",
        "notes/",
        json={
            "title": title,
            "description": description,
            "deal": deal,
            "invoice": invoice,
            "recurring_invoice": recurring_invoice,
        },
    )
    _echo_json(data) if as_json else _echo_notes([data])


@cli.group()
def services():
    """Look at services and the hours and costs logged on them"""


@services.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--json", "as_json", is_flag=True)
def search_services(query, project, offer, as_json):
    """Search services, ordered by project and offer"""
    params = {"q": " ".join(query)}
    if project:
        params["project"] = project
    if offer:
        params["offer"] = offer
    data = _request("GET", "services/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table(
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
    for service in data:
        notes = [
            note
            for note, flag in [
                ("optional", service["is_optional"]),
                ("no logging", not service["is_logging_allowed"]),
            ]
            if flag
        ]
        table.add_row(
            _link(service["id"], service["url"]),
            _link(service["project"]["code"], service["project"]["url"]),
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


@cli.group()
def hours():
    """Look at logged hours, log them in Workbench"""


@hours.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.")
@click.option(
    "--since", type=click.DateTime(formats=["%Y-%m-%d"]), help="Rendered since."
)
@click.option(
    "--until", type=click.DateTime(formats=["%Y-%m-%d"]), help="Rendered until."
)
@click.option("--json", "as_json", is_flag=True)
def search_hours(
    query, project, customer, offer, service, rendered_by, since, until, as_json
):
    """Search logged hours, newest first"""
    params = {"q": " ".join(query)}
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    if since:
        params["rendered_since"] = since.date().isoformat()
    if until:
        params["rendered_until"] = until.date().isoformat()
    data = _request("GET", "logbook/hours/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Rendered on",
        "By",
        "Project",
        "Service",
        "Hours>",
        "Description",
        show_footer=True,
    )
    for row in data["hours"]:
        table.add_row(
            _link(row["rendered_on"], row["url"]),
            row["rendered_by"],
            _link(row["project"]["code"], row["project"]["url"]),
            row["service"],
            row["hours"],
            row["description"],
        )
    table.columns[0].footer = "Total"
    table.columns[4].footer = data["total_hours"]
    console.print(table)
    if data["count"] > len(data["hours"]):
        console.print(
            f"Showing {len(data['hours'])} of {data['count']} entries,"
            " the total includes all of them."
        )


@cli.group()
def absences():
    """Look at absences"""


@absences.command("search")
@click.option("--user", help="Short name.")
@click.option(
    "--reason",
    type=click.Choice([
        "vacation",
        "sickness",
        "paid",
        "school",
        "other",
        "correction",
    ]),
)
@click.option(
    "--since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Absences ending on or after this date, defaults to today.",
)
@click.option(
    "--until",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Absences starting on or before this date.",
)
@click.option("--json", "as_json", is_flag=True)
def search_absences(user, reason, since, until, as_json):
    """Search absences, current and upcoming ones by default"""
    params = {"since": (since.date() if since else dt.date.today()).isoformat()}
    if user:
        params["user"] = user
    if reason:
        params["reason"] = reason
    if until:
        params["until"] = until.date().isoformat()
    data = _request("GET", "absences/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table("User", "Starts on", "Ends on", "Days>", "Reason", "Description")
    for absence in data:
        table.add_row(
            _link(absence["user"], absence["url"]),
            absence["starts_on"],
            absence["ends_on"] or "",
            absence["days"],
            absence["reason"],
            absence["description"],
        )
    console.print(table)


@cli.group()
def costs():
    """Look at logged costs, log them in Workbench"""


@costs.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.")
@click.option("--expenses", is_flag=True, help="Paid from someone's own pocket.")
@click.option(
    "--since", type=click.DateTime(formats=["%Y-%m-%d"]), help="Rendered since."
)
@click.option(
    "--until", type=click.DateTime(formats=["%Y-%m-%d"]), help="Rendered until."
)
@click.option("--json", "as_json", is_flag=True)
def search_costs(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    expenses,
    since,
    until,
    as_json,
):
    """Search logged costs, newest first"""
    params = {"q": " ".join(query), "expenses": _bool(expenses)}
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    if since:
        params["rendered_since"] = since.date().isoformat()
    if until:
        params["rendered_until"] = until.date().isoformat()
    data = _request("GET", "logbook/costs/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Rendered on",
        "By",
        "Project",
        "Service",
        "Cost>",
        "Third party>",
        "Description",
        show_footer=True,
    )
    for row in data["costs"]:
        table.add_row(
            _link(row["rendered_on"], row["url"]),
            row["rendered_by"],
            _link(row["project"]["code"], row["project"]["url"]),
            row["service"],
            row["cost"],
            row["third_party_costs"] or "",
            row["description"] + (" (expenses)" if row["are_expenses"] else ""),
        )
    table.columns[0].footer = "Total"
    table.columns[4].footer = data["total_cost"]
    table.columns[5].footer = data["total_third_party_costs"]
    console.print(table)
    if data["count"] > len(data["costs"]):
        console.print(
            f"Showing {len(data['costs'])} of {data['count']} entries,"
            " the totals include all of them."
        )


@cli.group("projected-invoices")
def projected_invoices():
    """Look at the planned invoicing"""


@projected_invoices.command("search")
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option(
    "--since", type=click.DateTime(formats=["%Y-%m-%d"]), help="Invoiced since."
)
@click.option(
    "--until", type=click.DateTime(formats=["%Y-%m-%d"]), help="Invoiced until."
)
@click.option("--json", "as_json", is_flag=True)
def search_projected_invoices(project, customer, since, until, as_json):
    """Search the planned invoicing (gross margin), oldest first"""
    params = {}
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    if since:
        params["invoiced_since"] = since.date().isoformat()
    if until:
        params["invoiced_until"] = until.date().isoformat()
    data = _request("GET", "projected-invoices/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table("Project", "Invoiced on", "Gross margin>", "Description")
    for row in data:
        table.add_row(
            _link(row["project"]["code"], row["project"]["url"]),
            row["invoiced_on"],
            row["gross_margin"],
            row["description"],
        )
    console.print(table)


@cli.group()
def deals():
    """Look at and add to the sales pipeline"""


@deals.command("search")
@click.argument("query", nargs=-1)
@click.option(
    "--status", type=click.Choice(["open", "accepted", "declined"]), default="open"
)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.")
@click.option("--json", "as_json", is_flag=True)
def search_deals(query, status, customer, owned_by, as_json):
    """Search deals, open deals by default"""
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
            _link(deal["customer"]["name"], deal["customer"]["url"]),
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
    _echo_json(data) if as_json else _echo_deal(data)


def _key_values(values, option):
    """Parse ``KEY=VALUE`` options into a dict"""
    result = {}
    for pair in values:
        key, sep, value = pair.partition("=")
        if not sep:
            _terminate(f"{option} expects KEY=VALUE, got {pair!r}.")
        result[key.strip()] = value.strip()
    return result


@deals.command("create")
@click.option("--title", required=True)
@click.option(
    "--customer", type=int, help="Organization ID, defaults to the contact's."
)
@click.option("--contact", type=int, help="Person ID.")
@click.option(
    "--probability", type=click.Choice(["low", "normal", "high"]), required=True
)
@click.option(
    "--decision-expected-on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Required for a high probability.",
)
@click.option("--value", "values", multiple=True, help="TYPE=AMOUNT, e.g. Design=5000.")
@click.option("--attribute", "attributes", multiple=True, help="GROUP=ATTRIBUTE.")
@click.option("--owned-by", help="Short name, defaults to you.")
@click.option("--description", default="")
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_deal(
    title,
    customer,
    contact,
    probability,
    decision_expected_on,
    values,
    attributes,
    owned_by,
    description,
    dry_run,
    as_json,
):
    """Create a deal, you are its main driving force

    Find the customer and the contact with `wb contacts search`. Unknown
    value types and attributes are rejected with a list of the choices."""
    data = _request(
        "POST",
        "deals/",
        params={"dry_run": _bool(dry_run)},
        json={
            "title": title,
            "description": description,
            "customer": customer,
            "contact": contact,
            "owned_by": owned_by,
            "probability": probability,
            "decision_expected_on": decision_expected_on.date().isoformat()
            if decision_expected_on
            else None,
            "values": _key_values(values, "--value"),
            "attributes": _key_values(attributes, "--attribute"),
        },
    )
    if as_json:
        _echo_json(data)
        return
    _echo_deal(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


def _echo_deal(data):
    _echo_fields(
        f"{data['code'] or '(new deal)'} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", _link(data["customer"]["name"], data["customer"]["url"])),
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
def timestamps():
    """Start and stop tasks, log the hours in Workbench"""


def _time(value):
    """Hours and minutes of an ISO 8601 timestamp in Workbench's time zone"""
    return dt.datetime.fromisoformat(value).strftime("%H:%M") if value else "?"


def _create_timestamp(type_, args, as_json):
    """The first argument may be a time (13:30) or minutes relative to now
    (-5, +15), the others are notes"""
    data = {"type": type_}
    if args and re.fullmatch(r"[0-9]{1,2}:[0-9]{2}", args[0]):
        data["time"] = args[0]
        args = args[1:]
    elif args and re.fullmatch(r"[-+][0-9]+", args[0]):
        data["minutes"] = int(args[0])
        args = args[1:]
    data["notes"] = " ".join(args)
    timestamp = _request("POST", "timestamps/", json=data)
    if as_json:
        _echo_json(timestamp)
        return
    console.print(
        f"{timestamp['type'].capitalize()} at {_time(timestamp['created_at'])}"
        + (f": {timestamp['notes']}" if timestamp["notes"] else "")
    )


_TIMESTAMP_HELP = """

    \b
    wb timestamps {0}                   # Now
    wb timestamps {0} -5 Notes          # 5 minutes ago, with notes
    wb timestamps {0} 13:30             # At 13:30
    wb timestamps {0} +15               # In 15 minutes"""


@timestamps.command(
    context_settings={"ignore_unknown_options": True},
    help="Start a task" + _TIMESTAMP_HELP.format("start"),
)
@click.argument("args", nargs=-1)
@click.option("--json", "as_json", is_flag=True)
def start(args, as_json):
    _create_timestamp("start", args, as_json)


@timestamps.command(
    context_settings={"ignore_unknown_options": True},
    help="Stop a task" + _TIMESTAMP_HELP.format("stop"),
)
@click.argument("args", nargs=-1)
@click.option("--json", "as_json", is_flag=True)
def stop(args, as_json):
    _create_timestamp("stop", args, as_json)


@timestamps.command("list")
@click.option(
    "--day", type=click.DateTime(formats=["%Y-%m-%d"]), help="Defaults to today."
)
@click.option("--json", "as_json", is_flag=True)
def list_timestamps(day, as_json):
    """The day's timestamps, logged hours and breaks

    Unlogged slices link to the form for logging their hours."""
    params = {"day": day.date().isoformat()} if day else {}
    data = _request("GET", "timestamps/", params=params)
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "From",
        "Until",
        "Hours>",
        "Description",
        "Project",
        "",
        title=_link(f"Timestamps {data['day']}", data["url"]),
        show_footer=True,
    )
    for slice in data["slices"]:
        project = slice["project"]
        table.add_row(
            _time(slice["starts_at"]),
            _time(slice["ends_at"]),
            slice["hours"] or "",
            slice["description"] + (f" {slice['comment']}" if slice["comment"] else ""),
            _link(project["code"], project["url"]) if project else "",
            _link("Log hours", slice["log_hours_url"])
            if slice["log_hours_url"]
            else "",
            style=None if slice["is_logged"] else "bold",
        )
    table.columns[1].footer = "Logged"
    table.columns[2].footer = data["logged_hours"]
    console.print(table)


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
