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
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlsplit

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
        "ID>", "Service", "Effort type", "Hours>", "Rate>", "Cost>", show_footer=True
    )
    for service in offer["services"]:
        table.add_row(
            str(service["id"] or "(new)"),
            service["title"] + (" (optional)" if service["is_optional"] else ""),
            service["effort_type"],
            service["effort_hours"] or "",
            service["effort_rate"] or "",
            service["service_cost"],
            style="dim" if service["is_optional"] else None,
        )
    table.columns[1].footer = "Subtotal"
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


def _page_options(fn):
    fn = click.option(
        "--offset",
        type=click.IntRange(min=0),
        default=0,
        help="Skip this many results.",
    )(fn)
    return click.option(
        "--limit",
        type=click.IntRange(1, 10000),
        help="Results per page, defaults to 100, at most 10000.",
    )(fn)


def _page_params(limit, offset):
    return {
        key: value for key, value in [("limit", limit), ("offset", offset)] if value
    }


def _echo_more(data, offset, what="results", *, note=""):
    """Tell how many results there are if not all of them are shown"""
    shown = len(data["items"])
    if not offset and shown == data["count"]:
        return
    if shown:
        message = f"Showing {offset + 1}–{offset + shown} of {data['count']} {what}"
    else:
        message = f"No {what} after the first {offset} of {data['count']}"
    if offset + shown < data["count"]:
        message += f", use --offset {offset + shown} for more"
    click.secho(f"{message}. {note}".strip(), fg="yellow", err=True)


def _period_options(default):
    """Options for the period of a report or a search, ``default`` describes
    it"""

    def decorator(fn):
        for option in reversed([
            click.option(
                "--period",
                help="Year (2026), month (2026-09), quarter (2026-Q3) or relative:"
                " last-, this- or next-week, -month, -quarter or -year;"
                f" {default}.",
            ),
            click.option(
                "--since",
                type=click.DateTime(formats=["%Y-%m-%d"]),
                help="Start of the period, overrides the period's start.",
            ),
            click.option(
                "--until",
                "until",
                type=click.DateTime(formats=["%Y-%m-%d"]),
                help="End of the period, overrides the period's end.",
            ),
        ]):
            fn = option(fn)
        return fn

    return decorator


def _users_options(fn):
    fn = click.option("--team", help="Team name.")(fn)
    return click.option(
        "--user", "users", multiple=True, help="Short name, can be repeated."
    )(fn)


def _period_params(period, since, until, *, users=(), team=None):
    params = {"period": period, "user": list(users), "team": team}
    if since:
        params["since"] = since.date().isoformat()
    if until:
        params["until"] = until.date().isoformat()
    return {key: value for key, value in params.items() if value}


def _number(value, places):
    """Format decimals (strings in the API) and numbers"""
    return f"{float(value):.{places}f}" if value is not None else ""


def _amount(value):
    return _number(value, 2)


def _hours(value):
    return _number(value, 1)


def _days(value):
    return _number(value, 1)


def _percentage(value):
    return f"{_number(value, 0)}%" if value is not None else ""


def _echo_period(data):
    console.print(f"{data['since']} – {data['until']}", style="bold")


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
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_users(query, include_inactive, limit, offset, as_json):
    """Search users by name, short name or email address, active users by
    default"""
    params = {"q": " ".join(query), "include_inactive": _bool(include_inactive)}
    data = _request("GET", "users/", params=params | _page_params(limit, offset))
    if as_json:
        _echo_json(data)
        return
    table = _table("ID>", "Short name", "Name", "Email", "Teams")
    for user in data["items"]:
        table.add_row(
            _link(user["id"], user["url"]),
            user["short_name"],
            _link(user["full_name"], user["url"])
            + ("" if user["is_active"] else " (inactive)"),
            user["email"],
            ", ".join(user["teams"]),
        )
    console.print(table)
    _echo_more(data, offset, "users")


@cli.group()
def projects():
    """Find and create projects"""


@projects.command()
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.")
@click.option("--all", "include_closed", is_flag=True, help="Include closed projects.")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search(query, customer, owned_by, include_closed, limit, offset, as_json):
    """Search projects, open projects by default"""
    params = {"q": " ".join(query), "include_closed": _bool(include_closed)}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = _request("GET", "projects/", params=params | _page_params(limit, offset))
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
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_contacts(query, include_archived, limit, offset, as_json):
    """Search organizations and people"""
    params = {"q": " ".join(query), "include_archived": _bool(include_archived)}
    organizations = _request(
        "GET", "contacts/organizations/", params=params | _page_params(limit, offset)
    )
    people = _request(
        "GET", "contacts/people/", params=params | _page_params(limit, offset)
    )
    if as_json:
        _echo_json({"organizations": organizations, "people": people})
        return
    table = _table("ID>", "Organization", title="Organizations")
    for organization in organizations["items"]:
        url = organization["url"]
        table.add_row(
            _link(organization["id"], url),
            _link(organization["name"], url)
            + (" (archived)" if organization["is_archived"] else ""),
        )
    console.print(table)
    _echo_more(organizations, offset, "organizations")
    table = _table("ID>", "Name", "Organization ID>", "Organization", title="People")
    for person in people["items"]:
        organization = person["organization"] or {}
        table.add_row(
            _link(person["id"], person["url"]),
            _link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
            _link(organization.get("id", ""), organization.get("url")),
            _link(organization.get("name", ""), organization.get("url")),
        )
    console.print(table)
    _echo_more(people, offset, "people")


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
@_period_options("filters the offer date")
@_page_options
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
    if dry_run:
        click.secho("Dry run, nothing has been saved.", fg="yellow", err=True)


def _text(value):
    """Texts given as ``-`` are read from stdin"""
    return sys.stdin.read() if value == "-" else value


@offers.command("update")
@click.argument("offer_id", type=int)
@click.option("--title")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def update_offer(offer_id, title, description, dry_run, as_json):
    """Change the title or the description of an offer in preparation"""
    data = {
        key: value
        for key, value in [("title", title), ("description", _text(description))]
        if value is not None
    }
    if not data:
        _terminate("Nothing to change, pass --title or --description.")
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


@cli.group()
def planning():
    """Plan projects: milestones and planned work"""


@planning.command("export")
@click.option("--project", type=int, help="Project ID.")
@click.option("--campaign", type=int, help="Campaign ID.")
@_period_options(
    "defaults to the whole planning of projects and campaigns, otherwise"
    " to the next twelve weeks"
)
@_users_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per work and week.")
@click.option("--json", "as_json", is_flag=True)
def planning_export(
    project, campaign, period, since, until, users, team, as_csv, as_json
):
    """Export planned work, milestones and the capacity per week

    The capacity (hours not planned yet, less absences and holidays) is shown
    when filtering by users or a team."""
    params = _period_params(period, since, until, users=users, team=team)
    if project:
        params["project"] = project
    if campaign:
        params["campaign"] = campaign
    data = _request("GET", "planning/export/", params=params)
    if as_json:
        _echo_json(data)
    elif as_csv:
        _echo_planning_csv(data)
    else:
        _echo_planning(data)


def _echo_planning_csv(data):
    weeks = {week["week"] for week in data["weeks"]}
    writer = csv.writer(sys.stdout)
    writer.writerow([
        "week",
        "project_id",
        "project",
        "project_title",
        "offer",
        "milestone",
        "work_id",
        "title",
        "user",
        "service_type",
        "is_provisional",
        "hours",
    ])
    rows = [
        (week, work)
        for work in data["planned_work"]
        for week in work["weeks"]
        if week in weeks
    ]
    for week, work in sorted(rows, key=lambda row: (row[0], row[1]["id"])):
        project = work["project"]
        writer.writerow([
            week,
            project["id"],
            project["code"],
            project["title"],
            work["offer"]["code"] if work["offer"] else "",
            work["milestone"] or "",
            work["id"],
            work["title"],
            work["user"],
            work["service_type"] or "",
            work["is_provisional"],
            work["hours_per_week"],
        ])


def _echo_planning(data):
    if not data["since"]:
        console.print("Nothing planned yet.")
        return
    _echo_period(data)
    table = _table(
        "Project",
        "Offer",
        "Title",
        "User",
        "First week",
        "Last week",
        "Hours>",
        "Per week>",
        title="Planned work",
    )
    for work in data["planned_work"]:
        project = work["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            work["offer"]["code"] if work["offer"] else "",
            _link(work["title"], work["url"]),
            work["user"],
            work["weeks"][0],
            work["weeks"][-1],
            _hours(work["planned_hours"]),
            _hours(work["hours_per_week"]),
            style="dim" if work["is_provisional"] else None,
        )
    console.print(table)
    if any(work["is_provisional"] for work in data["planned_work"]):
        console.print("Provisional work is dimmed.", style="dim")
    if data["milestones"]:
        table = _table("Date", "Project", "Milestone", "Hours>", title="Milestones")
        for milestone in data["milestones"]:
            table.add_row(
                milestone["date"],
                _link(milestone["project"]["code"], milestone["project"]["url"]),
                _link(milestone["title"], milestone["url"]),
                _hours(milestone["estimated_total_hours"]),
            )
        console.print(table)
    if data["external_work"]:
        table = _table(
            "Project",
            "Title",
            "Provided by",
            "First week",
            "Last week",
            title="External work",
        )
        for work in data["external_work"]:
            table.add_row(
                _link(work["project"]["code"], work["project"]["url"]),
                _link(work["title"], work["url"]),
                work["provided_by"],
                work["weeks"][0],
                work["weeks"][-1],
            )
        console.print(table)
    capacity = data["capacity"] or []
    table = _table(
        "Week",
        "Planned>",
        "Provisional>",
        *(f"{row['user']} free>" for row in capacity),
        title="Per week",
    )
    for week in data["weeks"]:
        table.add_row(
            week["week"],
            _hours(week["planned"]),
            _hours(week["provisional"]),
            *(_hours(row["weeks"][week["week"]]) for row in capacity),
        )
    console.print(table)


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
@_period_options("filters the invoice date")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_invoices(
    query,
    project,
    customer,
    status,
    open_,
    overdue,
    period,
    since,
    until,
    limit,
    offset,
    as_json,
):
    """Search invoices, newest first"""
    params = {"q": " ".join(query), "open": _bool(open_), "overdue": _bool(overdue)}
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    if status:
        params["status"] = status
    params |= _period_params(period, since, until)
    data = _request("GET", "invoices/", params=params | _page_params(limit, offset))
    if as_json:
        _echo_json(data)
        return
    _echo_invoice_list(data["items"])
    _echo_more(data, offset, "invoices")


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


@invoices.command("reminders")
@click.option("--json", "as_json", is_flag=True)
def invoice_reminders(as_json):
    """Overdue invoices to remind customers of, per customer and contact"""
    data = _request("GET", "invoices/reminders/")
    if as_json:
        _echo_json(data)
        return
    if not data:
        console.print("No overdue invoices.")
        return
    table = _table(
        "Code",
        "Title",
        "Invoiced on",
        "Due on",
        "Overdue>",
        "Last reminded on",
        "Total excl. tax>",
    )
    for group in data:
        contact = group["contact"]
        table.add_row(
            Text.assemble(
                _link(group["customer"]["name"], group["customer"]["url"]),
                " / ",
                _link(contact["full_name"], contact["url"])
                if contact
                else "(contact missing)",
                style="bold",
            ),
            "",
            "",
            "",
            "",
            "",
            group["total_excl_tax"],
            style="bold",
        )
        for invoice in group["invoices"]:
            table.add_row(
                _link(invoice["code"], invoice["url"]),
                invoice["title"],
                invoice["invoiced_on"],
                invoice["due_on"],
                f"{invoice['days_overdue']} days",
                invoice["last_reminded_on"] or "",
                invoice["total_excl_tax"],
            )
    console.print(table)


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
@_period_options("filters the creation date")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_notes(
    query,
    deal,
    invoice,
    recurring_invoice,
    created_by,
    period,
    since,
    until,
    limit,
    offset,
    as_json,
):
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
    params |= _period_params(period, since, until)
    data = _request("GET", "notes/", params=params | _page_params(limit, offset))
    if as_json:
        _echo_json(data)
    elif data["items"]:
        _echo_notes(data["items"])
        _echo_more(data, offset, "notes")
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
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_services(query, project, offer, limit, offset, as_json):
    """Search services, ordered by project and offer"""
    params = {"q": " ".join(query)}
    if project:
        params["project"] = project
    if offer:
        params["offer"] = offer
    data = _request("GET", "services/", params=params | _page_params(limit, offset))
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
    _echo_more(data, offset, "services")


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
@_period_options("filters the date the work was done")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_hours(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    period,
    since,
    until,
    limit,
    offset,
    as_json,
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
    params |= _period_params(period, since, until)
    data = _request(
        "GET", "logbook/hours/", params=params | _page_params(limit, offset)
    )
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
    for row in data["items"]:
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
    _echo_more(data, offset, "entries", note="The total includes all of them.")


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
@_period_options("absences overlapping it, current and upcoming ones by default")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_absences(user, reason, period, since, until, limit, offset, as_json):
    """Search absences, current and upcoming ones by default"""
    params = _period_params(period, since, until) or {
        "since": dt.date.today().isoformat()
    }
    if user:
        params["user"] = user
    if reason:
        params["reason"] = reason
    data = _request("GET", "absences/", params=params | _page_params(limit, offset))
    if as_json:
        _echo_json(data)
        return
    table = _table("User", "Starts on", "Ends on", "Days>", "Reason", "Description")
    for absence in data["items"]:
        table.add_row(
            _link(absence["user"], absence["url"]),
            absence["starts_on"],
            absence["ends_on"] or "",
            absence["days"],
            absence["reason"],
            absence["description"],
        )
    console.print(table)
    _echo_more(data, offset, "absences")


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
@_period_options("filters the date the work was done")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_costs(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    expenses,
    period,
    since,
    until,
    limit,
    offset,
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
    params |= _period_params(period, since, until)
    data = _request(
        "GET", "logbook/costs/", params=params | _page_params(limit, offset)
    )
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
    for row in data["items"]:
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
    _echo_more(data, offset, "entries", note="The totals include all of them.")


@cli.group("projected-invoices")
def projected_invoices():
    """Look at the planned invoicing"""


@projected_invoices.command("search")
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@_period_options("filters the planned invoice date")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_projected_invoices(
    project, customer, period, since, until, limit, offset, as_json
):
    """Search the planned invoicing (gross margin), oldest first"""
    params = _period_params(period, since, until)
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    data = _request(
        "GET", "projected-invoices/", params=params | _page_params(limit, offset)
    )
    if as_json:
        _echo_json(data)
        return
    table = _table("Project", "Invoiced on", "Gross margin>", "Description")
    for row in data["items"]:
        table.add_row(
            _link(row["project"]["code"], row["project"]["url"]),
            row["invoiced_on"],
            row["gross_margin"],
            row["description"],
        )
    console.print(table)
    _echo_more(data, offset, "projected invoices")


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
@_period_options("filters the decision date (closed or expected)")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_deals(
    query, status, customer, owned_by, period, since, until, limit, offset, as_json
):
    """Search deals, open deals by default"""
    params = {"q": " ".join(query), "status": status}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    params |= _period_params(period, since, until)
    data = _request("GET", "deals/", params=params | _page_params(limit, offset))
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
    for deal in data["items"]:
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
    _echo_more(data, offset, "deals")


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


@deals.command("stats")
@_period_options("defaults to this week")
@_users_options
@click.option("--json", "as_json", is_flag=True)
def deal_stats(period, since, until, users, team, as_json):
    """Deals accepted and declined in a period

    Users filter the deals' owners; accepted deals are split between users
    by their contributions."""
    data = _request(
        "GET",
        "deals/stats/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    accepted = data["accepted"]
    console.print(
        f"Accepted: {accepted['count']} deals, {_amount(accepted['sum'])}"
        + (
            f" (target {_amount(accepted['target'])})"
            if float(accepted["target"])
            else ""
        )
    )
    if accepted["deals"]:
        table = _table("Value type", "Accepted>", "Target>", "Median age>")
        for row in accepted["by_value_type"]:
            table.add_row(
                row["type"],
                _amount(row["sum"]),
                _amount(row["target"]),
                f"{row['median_age_days']} days"
                if row["median_age_days"] is not None
                else "",
            )
        console.print(table)
        table = _table("User", "Deals>", "Accepted>")
        for row in accepted["by_user"]:
            table.add_row(row["user"], str(row["count"]), _amount(row["sum"]))
        console.print(table)
        table = _table(
            "Code",
            "Title",
            "Customer",
            "Owner",
            "Closed on",
            "Value>",
            title="Accepted",
        )
        for deal in accepted["deals"]:
            table.add_row(
                _link(deal["code"], deal["url"]),
                deal["title"],
                _link(deal["customer"]["name"], deal["customer"]["url"]),
                deal["owned_by"],
                deal["closed_on"],
                _amount(deal["value"]),
            )
        console.print(table)
    declined = data["declined"]
    console.print(f"Declined: {declined['count']} deals, {_amount(declined['sum'])}")
    if declined["deals"]:
        table = _table(
            "Code", "Title", "Customer", "Closing type", "Value>", title="Declined"
        )
        for deal in declined["deals"]:
            table.add_row(
                _link(deal["code"], deal["url"]),
                deal["title"],
                _link(deal["customer"]["name"], deal["customer"]["url"]),
                deal["closing_type"],
                _amount(deal["value"]),
            )
        console.print(table)


@deals.command("history")
@_period_options("defaults to this week")
@_users_options
@click.option("--json", "as_json", is_flag=True)
def deal_history(period, since, until, users, team, as_json):
    """Changes of deals in a period, users filter who made them"""
    data = _request(
        "GET",
        "deals/history/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    for change in data["changes"]:
        deal = change["deal"]
        console.print(
            _link(f"{deal['code']} {deal['title']}", deal["url"])
            if deal
            else "(deleted deal)",
            style="bold",
        )
        console.print(
            f"{change['created_at'][:16].replace('T', ' ')}, {change['user']}",
            style="dim",
        )
        for text in change["changes"]:
            console.print(f"  {text}")


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
    _echo_timestamp(timestamp)


def _echo_timestamp(timestamp, prefix=""):
    """The timestamp and the duration of the task it stopped"""
    text = (
        f"{prefix}{timestamp['code']}: {timestamp['type']}"
        f" at {_time(timestamp['created_at'])}"
        + (f", {timestamp['notes']}" if timestamp["notes"] else "")
    )
    if (slice := timestamp["slice"]) and slice["hours"] and slice["ends_at"]:
        text += f" ({slice['hours']}h since {_time(slice['starts_at'])})"
    console.print(text)


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
    _echo_json(data) if as_json else _echo_timestamps(data)


def _echo_timestamps(data):
    table = _table(
        "Code",
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
            slice["timestamp_code"] or "",
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
    table.columns[2].footer = "Logged"
    table.columns[3].footer = data["logged_hours"]
    console.print(table)
    console.print(f"Logged this week: {data['weekly_hours']}h")
    if data["running_since"]:
        console.print(
            f"Running since {_time(data['running_since'])} ({data['running_hours']}h)",
            style="bold",
        )


def _echo_deleted(timestamp, as_json):
    """The deleted timestamp and the day's renumbered timestamps"""
    if as_json:
        _echo_json(timestamp)
        return
    _echo_timestamp(timestamp, "Deleted ")
    day = dt.datetime.fromisoformat(timestamp["created_at"]).date().isoformat()
    _echo_timestamps(_request("GET", "timestamps/", params={"day": day}))


@timestamps.command("delete")
@click.argument("timestamp")
@click.option(
    "--day",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Day of the code, defaults to today.",
)
@click.option("--json", "as_json", is_flag=True)
def delete_timestamp(timestamp, day, as_json):
    """Delete a timestamp by its code (T1, T2, ...) or its ID

    `wb timestamps list` shows the codes. Deleting a timestamp renumbers the
    following ones, the new codes are shown afterwards."""
    params = {"day": day.date().isoformat()} if day else {}
    _echo_deleted(
        _request("DELETE", f"timestamps/{quote(timestamp, safe='')}/", params=params),
        as_json,
    )


@timestamps.command()
@click.option("--json", "as_json", is_flag=True)
def undo(as_json):
    """Delete the latest timestamp of today"""
    _echo_deleted(_request("DELETE", "timestamps/latest/"), as_json)


@cli.group()
def reports():
    """Reports, most of them require the controlling feature"""


@reports.command("key-data")
@click.option("--month", help="Month like 2026-09, defaults to the last month.")
def key_data(month):
    """Key data of a month (JSON output)"""
    _echo_json(_request("GET", "key-data/", params={"month": month} if month else {}))


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


@reports.command("working-time")
@click.option("--year", type=int, help="Defaults to the current year.")
@click.option("--user", help="Short name, defaults to you.")
@click.option(
    "--all",
    "all_",
    is_flag=True,
    help="Everyone employed during the year, requires the controlling feature.",
)
@click.option("--weekly", is_flag=True, help="Show the hours per week.")
@click.option("--json", "as_json", is_flag=True)
def working_time(year, user, all_, weekly, as_json):
    """Annual working time: Target, logged hours, absences and balance

    The balance per week compares the working time to a target based on the
    working time per day, the employment and the holidays."""
    params = {
        "year": year,
        "user": user,
        "all": _bool(all_) if all_ else None,
        "weekly": _bool(weekly) if weekly else None,
    }
    data = _request(
        "GET",
        "reports/working-time/",
        params={key: value for key, value in params.items() if value},
    )
    if as_json:
        _echo_json(data)
        return
    for warning in data["warnings"]:
        click.secho(warning, fg="yellow", err=True)
    for row in data["users"]:
        console.print(f"{row['user']} {data['year']}", style="bold")
        totals = row["totals"]
        if weekly:
            table = _table(
                "Week", "Target>", "Logged>", "Absences>", "Balance>", "Running>"
            )
            for week in row["weeks"]:
                table.add_row(
                    week["week"],
                    _hours(week["target"]),
                    _hours(week["hours"]),
                    _hours(week["absences"]),
                    _hours(week["delta"]),
                    _hours(week["running_delta"]),
                )
            console.print(table)
            continue
        table = _table(
            "Month",
            "Employment>",
            "Target>",
            "Logged>",
            "Absences>",
            "Working time>",
            "Balance>",
            "Running>",
            "Vacation days>",
            "Sick days>",
            show_footer=True,
        )
        for month in row["months"]:
            table.add_row(
                month["month"],
                _percentage(month["percentage"]),
                _hours(month["target"]),
                _hours(month["hours"]),
                _hours(month["absences_time"]),
                _hours(month["working_time"]),
                _hours(month["balance"]),
                _hours(month["running_balance"]),
                _days(month["vacation_days"]),
                _days(month["sickness_days"]),
            )
        table.columns[0].footer = "Total"
        table.columns[1].footer = _percentage(totals["percentage"])
        table.columns[2].footer = _hours(totals["target"])
        table.columns[3].footer = _hours(totals["hours"])
        table.columns[4].footer = _hours(totals["absences_time"])
        table.columns[5].footer = _hours(totals["working_time"])
        table.columns[6].footer = _hours(totals["running_sum"])
        table.columns[8].footer = _days(totals["absence_vacation"])
        table.columns[9].footer = _days(totals["absence_sickness"])
        console.print(table)
        console.print(
            f"Vacation days: {_days(totals['available_vacation_days'])} available,"
            f" {_days(totals['vacation_days_credit'])} left"
        )
        console.print(
            f"Balance incl. vacation days left: {_hours(totals['balance'])}h"
            f" ({totals['balance_days']} days)",
            style="bold",
        )
        console.print()


@reports.command("projected-gross-margin")
@click.option("--json", "as_json", is_flag=True)
def projected_gross_margin(as_json):
    """Planned invoicing of open projects which hasn't been invoiced yet"""
    data = _request("GET", "reports/projected-gross-margin/")
    if as_json:
        _echo_json(data)
        return
    table = _table("Month", "Gross margin>", show_footer=True)
    for month, value in data["monthly"].items():
        table.add_row(month, _amount(value))
    table.columns[0].footer = "Total"
    table.columns[1].footer = _amount(sum(map(float, data["monthly"].values())))
    console.print(table)
    table = _table("Code", "Title", "Owner", "Projected>", "Invoiced>", "Not invoiced>")
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            row["owned_by"],
            _amount(row["projected_total"]),
            _amount(row["gross_margin"]),
            _amount(row["not_invoiced"]),
        )
    console.print(table)


@reports.command("budget")
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Cutoff date, defaults to today.",
)
@click.option("--owned-by", help="Short name, or 'inactive' for inactive users.")
@click.option("--internal", is_flag=True, help="Internal projects only.")
@click.option("--closed", is_flag=True, help="Projects closed during the last year.")
@click.option(
    "--filter",
    "filter_",
    type=click.Choice([
        "no-invoices",
        "maintenance",
        "old-projects",
        "no-projected-gross-margin",
    ]),
)
@click.option("--json", "as_json", is_flag=True)
def budget(date, owned_by, internal, closed, filter_, as_json):
    """Project budget statistics: Logged work compared to offers and invoices

    Delta is the logbook minus the invoiced amount, positive for work which
    hasn't been invoiced yet."""
    params = {
        "owned_by": owned_by,
        "internal": _bool(internal) if internal else None,
        "closed": _bool(closed) if closed else None,
        "filter": filter_,
    }
    if date:
        params["date"] = date.date().isoformat()
    data = _request(
        "GET",
        "reports/budget/",
        params={key: value for key, value in params.items() if value},
    )
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Code",
        "Title",
        "Owner",
        "Offered h>",
        "Logged h>",
        "Logbook>",
        "Sold>",
        "Invoiced>",
        "Delta>",
        "Projected>",
        show_footer=True,
    )
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            row["owned_by"],
            _hours(row["service_hours"]),
            _hours(row["hours"]),
            _amount(row["logbook"]),
            _amount(row["sold"]),
            _amount(row["invoiced"]),
            _amount(row["delta"]),
            _amount(row["projected_gross_margin"]),
        )
    overall = data["overall"]
    table.columns[0].footer = "Total"
    for index, key, fmt in [
        (3, "service_hours", _hours),
        (4, "hours", _hours),
        (5, "logbook", _amount),
        (6, "sold", _amount),
        (7, "invoiced", _amount),
        (9, "projected_gross_margin", _amount),
    ]:
        table.columns[index].footer = fmt(overall[key])
    console.print(table)
    console.print(
        f"Not invoiced yet: {_amount(overall['delta_positive'])},"
        f" accruals: {_amount(overall['delta_negative'])}"
    )


@reports.command("third-party-costs")
@click.option(
    "--this-year",
    is_flag=True,
    help="Also projects closed during the current year.",
)
@click.option("--json", "as_json", is_flag=True)
def third_party_costs(this_year, as_json):
    """Third party costs logged and invoiced per project

    Delta is positive for costs which haven't been invoiced yet."""
    data = _request(
        "GET",
        "reports/third-party-costs/",
        params={"this_year": _bool(this_year)} if this_year else {},
    )
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "Code",
        "Title",
        "Owner",
        "Offered>",
        "Logged>",
        "Logged (future)>",
        "Invoiced>",
        "Delta>",
        show_footer=True,
    )
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            row["owned_by"],
            _amount(row["offered"]),
            _amount(row["logged"]["past"]),
            _amount(row["logged"]["future"]),
            _amount(row["invoiced"]),
            _amount(row["delta"]),
        )
    table.columns[0].footer = "Total"
    table.columns[3].footer = _amount(data["total_offered"])
    table.columns[4].footer = _amount(data["total_logged"]["past"])
    table.columns[5].footer = _amount(data["total_logged"]["future"])
    table.columns[6].footer = _amount(data["total_invoiced"])
    console.print(table)
    console.print(
        f"Not invoiced yet: {_amount(data['total_not_invoiced'])},"
        f" invoiced too much: {_amount(data['total_invoiced_too_much'])}"
    )


@reports.command("open-items")
@click.option(
    "--date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Cutoff date, defaults to today.",
)
@click.option("--json", "as_json", is_flag=True)
def open_items(date, as_json):
    """Invoices sent but not paid on the cutoff date"""
    data = _request(
        "GET",
        "reports/open-items/",
        params={"date": date.date().isoformat()} if date else {},
    )
    if as_json:
        _echo_json(data)
        return
    _echo_invoice_list(data["invoices"])
    table = _table("Due in the week of", "Total excl. tax>", "Total>")
    for week in data["weeks"]:
        table.add_row(
            week["week"], _amount(week["total_excl_tax"]), _amount(week["total"])
        )
    console.print(table)
    console.print(
        f"Total excl. tax: {_amount(data['total_excl_tax'])},"
        f" total: {_amount(data['total'])}"
    )


@reports.command("hours-per-customer")
@_period_options("defaults to this week")
@_users_options
@click.option("--json", "as_json", is_flag=True)
def hours_per_customer(period, since, until, users, team, as_json):
    """Logged hours per customer and user"""
    data = _request(
        "GET",
        "reports/hours-per-customer/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "Customer", "Total>", *(f"{user}>" for user in data["users"]), show_footer=True
    )
    for row in data["customers"]:
        table.add_row(
            _link(row["customer"]["name"], row["customer"]["url"]),
            _hours(row["total_hours"]),
            *(_hours(row["users"].get(user)) for user in data["users"]),
        )
    table.columns[0].footer = "Total"
    table.columns[1].footer = _hours(data["total_hours"])
    for index, hours in enumerate(data["users"].values(), 2):
        table.columns[index].footer = _hours(hours)
    console.print(table)


@reports.command("hours-per-type")
@_period_options("defaults to this week")
@_users_options
@click.option("--json", "as_json", is_flag=True)
def hours_per_type(period, since, until, users, team, as_json):
    """Logged hours per user, external and per internal type

    Shows the percentage reached and expected (in parentheses)."""
    data = _request(
        "GET",
        "reports/hours-per-type/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    types = (
        [type["type"] for type in data["users"][0]["types"]] if data["users"] else []
    )
    table = _table("User", "Total>", *(f"{type}>" for type in types))
    for row in data["users"]:
        table.add_row(
            row["user"],
            _hours(row["total"]),
            *(
                f"{_hours(type['hours'])} {_percentage(type['reached_percentage'])}"
                f" ({_percentage(type['expected_percentage'])})"
                for type in row["types"]
            ),
        )
    console.print(table)


@reports.command("green-hours")
@_period_options("defaults to this week")
@_users_options
@click.option("--json", "as_json", is_flag=True)
def green_hours(period, since, until, users, team, as_json):
    """Profitable, overdrawn, maintenance and internal hours per user

    Green hours are profitable and maintenance hours."""
    data = _request(
        "GET",
        "reports/green-hours/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "User",
        "Profitable>",
        "Overdrawn>",
        "Maintenance>",
        "Internal>",
        "Total>",
        "Green>",
        show_footer=True,
    )

    def cells(row):
        return [
            _hours(row["profitable"]),
            _hours(row["overdrawn"]),
            _hours(row["maintenance"]),
            _hours(row["internal"]),
            _hours(row["total"]),
            _percentage(row["percentage"]),
        ]

    for row in data["users"]:
        table.add_row(row["user"], *cells(row))
    if data["total"]:
        table.columns[0].footer = "Total"
        for index, value in enumerate(cells(data["total"]), 1):
            table.columns[index].footer = value
    console.print(table)


@reports.command("planning-vs-logbook")
@_period_options("defaults to this week")
@_users_options
@click.option("--json", "as_json", is_flag=True)
def planning_vs_logbook(period, since, until, users, team, as_json):
    """Planned and logged hours per customer

    The allocation is the customer's share of the logged hours relative to
    its share of the planned hours."""
    data = _request(
        "GET",
        "reports/planning-vs-logbook/",
        params=_period_params(period, since, until, users=users, team=team),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "Customer", "Planned>", "Logged>", "Diff>", "Allocation>", show_footer=True
    )
    for row in data["customers"]:
        table.add_row(
            _link(row["customer"]["name"], row["customer"]["url"]),
            _hours(row["planned"]),
            _hours(row["logged"]),
            _hours(row["diff"]),
            _percentage(row["allocation"]),
        )
    table.columns[0].footer = "Total"
    table.columns[1].footer = _hours(data["planned"])
    table.columns[2].footer = _hours(data["logged"])
    table.columns[3].footer = _hours(data["diff"])
    table.columns[4].footer = _percentage(data["logged_percentage"])
    console.print(table)


@reports.command("logging")
@_period_options("defaults to this week")
@click.option("--json", "as_json", is_flag=True)
def logging_report(period, since, until, as_json):
    """How and when users log their hours, and insufficient breaks"""
    data = _request(
        "GET", "reports/logging/", params=_period_params(period, since, until)
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    table = _table(
        "User",
        "Entries>",
        "Hours>",
        "Per entry>",
        "Delay>",
        "Logging",
        "Breaks too short>",
    )
    for row in data["users"]:
        breaks = row["insufficient_breaks"]
        table.add_row(
            row["user"],
            str(row["logged_hours"]["count"]),
            _hours(row["logged_hours"]["sum"]),
            _hours(row["logged_hours"]["avg"]),
            f"{_number(row['mean_logging_delay_hours'], 0)}h",
            row["logging"],
            f"{len(breaks['days'])}/{breaks['of']} days",
            style="red" if breaks["warning"] else None,
        )
    console.print(table)


@reports.command("squeeze")
@_period_options("defaults to the last month")
@click.option("--json", "as_json", is_flag=True)
def squeeze(period, since, until, as_json):
    """Gross margin per user and project, requires the productivity feature

    Projects' gross margins are split between users by hours weighted with
    the hourly rate. The delta compares the gross margin to the expected
    gross margin."""
    data = _request(
        "GET", "reports/squeeze/", params=_period_params(period, since, until)
    )
    if as_json:
        _echo_json(data)
        return
    _echo_period(data)
    if data["may_be_incomplete"]:
        click.secho(
            "Invoices for the selected period may not be complete yet.",
            fg="yellow",
            err=True,
        )
    table = _table(
        "User",
        "Hours>",
        "Gross margin>",
        "Rate>",
        "Expected>",
        "Delta>",
        "External>",
        show_footer=True,
    )

    def cells(row):
        return [
            _hours(row["hours_in_range"]),
            _amount(row["gross_margin"]),
            _amount(row["rate"]),
            _amount(row["expected_gross_margin"]),
            _amount(row["delta"]),
            _percentage(row["external_percentage"]),
        ]

    for row in data["users"]:
        table.add_row(row["user"], *cells(row))
    table.columns[0].footer = "Total"
    for index, value in enumerate(cells(data["totals"]), 1):
        table.columns[index].footer = value
    console.print(table)
    table = _table("Code", "Title", "Hours>", "Gross margin>", "Rate>", "Users")
    for row in data["projects"]:
        project = row["project"]
        table.add_row(
            _link(project["code"], project["url"]),
            project["title"],
            _hours(row["hours_in_range"]),
            _amount(row["gross_margin_in_range"]),
            _amount(row["rate"]),
            ", ".join(row["users"]),
        )
    console.print(table)
