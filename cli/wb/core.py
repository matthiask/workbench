"""The Workbench CLI"""

import csv
import datetime as dt
import json
import os
import platform
import secrets
import shlex
import socket
import sys
import tempfile
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
import tomli_w
import yaml
from click.shell_completion import CompletionItem
from rich import box
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text


CONFIG = Path.home() / ".config" / "workbench.toml"


BUG_REPORTS = Path.home() / ".cache" / "wb"


CACHE = Path.home() / ".cache" / "wb"


# Short names and teams for completing options change rarely
COMPLETION_TTL = 24 * 60 * 60


def _version():
    """The version of the checkout for editable installs, their metadata
    keeps the version they were installed with"""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    if pyproject.exists():
        return tomllib.loads(pyproject.read_text())["project"]["version"]
    return version("workbench-cli")


VERSION = _version()


console = Console(markup=False, highlight=False)


def terminate(msg):
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
        url = (
            installation_url(os.environ.get("WORKBENCH_URL"))
            or read_config()["current"]
        )
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
        terminate(
            f"{problem} Please send this to the people running Workbench:\n\n{report}"
        )
    terminate(
        f"{problem} Please send {path} to the people running Workbench"
        " and tell them what you tried to do."
    )


class _Group(click.Group):
    """Commands which crash write a bug report instead of a traceback, set
    WB_DEBUG to get the exception

    ``aliases`` maps short names to commands, the help lists them
    separately."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aliases = {}

    def get_command(self, ctx, cmd_name):
        return super().get_command(ctx, self.aliases.get(cmd_name, cmd_name))

    def resolve_command(self, ctx, args):
        # Show the full name in usage and error messages
        _name, command, args = super().resolve_command(ctx, args)
        return command.name if command else None, command, args

    def format_commands(self, ctx, formatter):
        super().format_commands(ctx, formatter)
        if self.aliases:
            with formatter.section("Aliases"):
                formatter.write_dl(sorted(self.aliases.items()))

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


def read_config():
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
        key=lambda item: item[0] == installation_url(item[0]),
    ):
        installations[installation_url(url)] = installation
    return {
        "current": installation_url(config.get("current")),
        "installations": installations,
    }


def installation_url(url):
    """The scheme and the host which identify an installation, URLs may be
    pasted from the browser"""
    if not url:
        return url
    if "://" not in url:
        url = f"https://{url}"
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc.lower()}"


def write_config(config):
    """TOML has no null, leave out empty values"""
    data = {"current": config["current"]} if config["current"] else {}
    data["installations"] = {
        url: {key: value for key, value in installation.items() if value}
        for url, installation in sorted(config["installations"].items())
    }
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates the file readable by its owner only. Replacing the
    # configuration with it means nobody ever sees a half-written file.
    fd, path = tempfile.mkstemp(
        dir=CONFIG.parent, prefix=f".{CONFIG.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(tomli_w.dumps(data))
        os.replace(path, CONFIG)
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise


def save_config(url, token, access=None):
    """Store the token of the installation and make it the current one

    The access is remembered to ask for the same access when the token
    expires; it is unknown for pasted tokens."""
    config = read_config()
    # Keep the other settings of the installation, but not the access of
    # the old token
    previous = config["installations"].get(url, {})
    config["installations"][url] = (
        {key: value for key, value in previous.items() if key != "access"}
        | {"token": token}
        | ({"access": access} if access else {})
    )
    config["current"] = url
    write_config(config)


# The installation selected with --installation for this invocation, and
# whether wb already said which installation it uses
_selected_installation = None
_announced = False


def current_installation():
    """The URL of the installation commands talk to: --installation, then
    WORKBENCH_URL (e.g. for one terminal), then the current one"""
    return (
        _selected_installation
        or installation_url(os.environ.get("WORKBENCH_URL"))
        or read_config()["current"]
    )


def find_installation(name):
    """The URL of the installation NAME is a unique part of"""
    urls = sorted(read_config()["installations"])
    matches = [url for url in urls if url == name] or [
        url for url in urls if name in url
    ]
    if len(matches) != 1:
        terminate(
            f"{'Several' if matches else 'No'} installations match {name!r}:"
            f" {', '.join(matches or urls) or '(none)'}. Add new ones with"
            " `wb login URL`."
        )
    return matches[0]


def complete_installations(ctx, param, incomplete):
    # Host names only: bash splits words at the colon of https://
    return [
        CompletionItem(host)
        for host in sorted(
            urlsplit(url).netloc for url in read_config()["installations"]
        )
        if incomplete in host
    ]


def _select_installation(ctx, param, value):
    global _selected_installation, _announced  # noqa: PLW0603
    _selected_installation = find_installation(value) if value else None
    _announced = False


def announce_installation(url):
    """Say once when a command doesn't use the current installation, on
    stderr to keep the output clean"""
    global _announced  # noqa: PLW0603
    current = read_config()["current"]
    if _announced or not current or url == current:
        return
    _announced = True
    source = "--installation" if _selected_installation else "WORKBENCH_URL"
    click.secho(
        f"Using {url} ({source}), not the current {current}.", fg="yellow", err=True
    )


def _config():
    """URL and token of the current installation

    WORKBENCH_URL selects another installation wb is logged in to, e.g. for
    the commands of one terminal."""
    url = current_installation()
    token = read_config()["installations"].get(url, {}).get("token")
    if not url or not token:
        terminate("Not configured yet. Run `wb login URL` first.")
    announce_installation(url)
    return url, token


def _can_login_again(url):
    """The access to ask for again when the token expires, if any

    Expired tokens are replaced through the browser, but only for people
    sitting in front of a terminal and only with the same access as before."""
    if not sys.stdin.isatty():
        return None
    return read_config()["installations"].get(url, {}).get("access")


LOGIN_TIMEOUT = 300


def browser_login(url, access):
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
            "access": access,
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
        terminate("Timed out waiting for the browser.")
    save_config(url, result["token"], access)
    click.echo(f"Saved {CONFIG}", err=True)
    return result["token"]


def _parse_version(version):
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return ()


@cache
def _check_version(latest, upgrade):
    """Tell the user about a newer version, or that the Workbench is older
    than the CLI and may not support everything yet, once

    ``latest`` is the version of the CLI in the Workbench's checkout,
    ``upgrade`` the command which upgrades to it (it may need a newer
    Python)."""
    if not latest:
        return
    if _parse_version(latest) > _parse_version(VERSION):
        upgrade = upgrade or "uv tool upgrade workbench-cli"
        click.secho(
            f"wb {latest} is available (you have {VERSION}): {upgrade}",
            fg="yellow",
            err=True,
        )
    elif _parse_version(latest) < _parse_version(VERSION):
        click.secho(
            f"This Workbench is older than your wb ({latest} < {VERSION}),"
            " some commands may fail until it is updated.",
            fg="yellow",
            err=True,
        )


def format_error(error):
    """A validation error, prefixed with the field if there is one; warnings
    of the web interface tell how to ignore them"""
    message = error["msg"]
    if code := error.get("code"):
        message = f"{message} (warning, ignore with --ignore-warning {code})"
    if loc := ".".join(str(part) for part in error["loc"][2:]):
        return f"{loc}: {message}"
    return message


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
        terminate(str(exc))


def request(method, path, *, optional=False, **kwargs):
    """Request the API, terminate on errors

    ``optional`` requests return ``None`` if access is denied, e.g. because
    a feature is missing. Expired tokens are replaced and the request is
    sent again."""
    url, token = _config()
    response = _send(method, url, path, token, **kwargs)
    if response.status_code == 401 and (access := _can_login_again(url)):
        click.secho("Your access has expired.", fg="yellow", err=True)
        token = browser_login(url, access)
        response = _send(method, url, path, token, **kwargs)
    _check_version(
        response.headers.get("x-workbench-cli-latest"),
        response.headers.get("x-workbench-cli-upgrade"),
    )
    if response.status_code == 401:
        terminate("Not authorized (anymore). Run `wb login` to log in again.")
    if response.status_code == 403 and optional:
        return None
    if response.status_code == 422:
        terminate("\n".join(format_error(error) for error in response.json()["detail"]))
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
        terminate(f"{response.status_code}: {detail}")
    return response.json()


class _Loader(yaml.SafeLoader):
    """Keeps dates as strings, the server parses them"""


_Loader.yaml_implicit_resolvers = {
    key: [r for r in resolvers if r[0] != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def load(file):
    """Load data from a YAML or JSON file"""
    try:
        return yaml.load(file, Loader=_Loader)
    except yaml.YAMLError as exc:
        terminate(f"Invalid YAML or JSON: {exc}")


def format_bool(value):
    return "true" if value else "false"


def echo_json(data):
    click.echo(json.dumps(data, indent=2, ensure_ascii=False))


def link(text, url):
    """Text which links to the URL in terminals supporting hyperlinks"""
    return Text(str(text), style=Style(link=url)) if url else str(text)


def make_table(*columns, **kwargs):
    """A table with headings, columns ending in ">" are right-aligned"""
    table = Table(box=box.SIMPLE_HEAD, **kwargs)
    for column in columns:
        if column.endswith(">"):
            table.add_column(column[:-1], justify="right")
        else:
            table.add_column(column)
    return table


def echo_fields(title, fields, *, url=None):
    """A bold title followed by the non-empty fields"""
    console.print(link(title, url), style="bold")
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim")
    grid.add_column()
    for label, value in fields:
        if value:
            grid.add_row(label, value if isinstance(value, Text) else str(value))
    console.print(grid)


def echo_offer(offer):
    echo_fields(
        f"{offer['code'] or '(new offer)'} {offer['title']}",
        [
            ("ID", offer["id"]),
            ("Status", offer["status"]),
            ("Offered on", offer.get("offered_on")),
            ("Valid until", offer.get("valid_until")),
            ("Closed on", offer.get("closed_on")),
            ("Work completed on", offer.get("work_completed_on")),
            ("External reference", offer.get("external_reference")),
            ("URL", offer["url"]),
        ],
        url=offer["url"],
    )
    table = make_table(
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


def echo_offer_list(offers, *, title=None):
    if not offers:
        console.print("No offers yet.")
        return
    table = make_table("ID>", "Code", "Title", "Status", "Total>", title=title)
    for offer in offers:
        table.add_row(
            link(offer["id"], offer["url"]),
            link(offer["code"], offer["url"]),
            offer["title"],
            offer["status"],
            offer["total"],
        )
    console.print(table)


def echo_stats(projects):
    table = make_table(
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
            link(project["code"], project["url"]),
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


def echo_stats_csv(projects):
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


def echo_deal_list(deals, *, title=None):
    table = make_table(
        "ID>", "Title", "Customer", "Decision expected on", "Value>", title=title
    )
    for deal in deals:
        table.add_row(
            link(deal["id"], deal["url"]),
            deal["title"],
            link(deal["customer"]["name"], deal["customer"]["url"]),
            deal["decision_expected_on"] or "",
            deal["value"],
        )
    console.print(table)


def me():
    """The authenticated user"""
    return request("GET", "me/")


def echo_actionable(key, feature):
    """Echo the offers, invoices or deals of ``wb me`` which may need action,
    the default of their nouns"""
    items = request("GET", "me/overview/")[key]
    if items is None:
        terminate(f"Requires the {feature} feature.")
    if not items:
        console.print(f"No {key} which may need action.")
        return
    {
        "offers": lambda: echo_offer_list(items, title="Offers which may need action"),
        "invoices": lambda: echo_invoice_list(
            items, title="Invoices which may need action"
        ),
        "deals": lambda: echo_deal_list(items, title="Deals which may need action"),
    }[key]()


def echo_invoice_list(invoices, *, title="Invoices"):
    table = make_table(
        "ID>",
        "Code",
        "Title",
        "Customer",
        "Status",
        "Invoiced on",
        "Due on",
        "Total excl. tax>",
        title=title,
    )
    for invoice in invoices:
        table.add_row(
            link(invoice["id"], invoice["url"]),
            link(invoice["code"], invoice["url"]),
            invoice["title"],
            link(invoice["customer"]["name"], invoice["customer"]["url"]),
            invoice["status"],
            invoice["invoiced_on"] or "",
            invoice["due_on"] or "",
            invoice["total_excl_tax"],
        )
    console.print(table)


ignore_warnings_option = click.option(
    "--ignore-warning",
    "ignore_warnings",
    multiple=True,
    metavar="CODE",
    help="Ignore this warning of the web interface (the code is shown with"
    " the warning), may be repeated.",
)


def page_options(fn):
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


def page_params(limit, offset):
    return {
        key: value for key, value in [("limit", limit), ("offset", offset)] if value
    }


def echo_more(data, offset, what="results", *, note=""):
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


def _completion_values(name, path, key):
    """Values for completing options, fetched from the API at most once a day
    per installation; no values if anything fails"""
    url = current_installation()
    token = read_config()["installations"].get(url, {}).get("token")
    if not url or not token:
        return []
    cache = CACHE / f"completion-{urlsplit(url).netloc}-{name}.json"
    try:
        if time.time() - cache.stat().st_mtime < COMPLETION_TTL:
            return json.loads(cache.read_text())
    except OSError, ValueError:
        pass
    try:
        response = requests.request(
            "GET",
            urljoin(url, f"/api/{path}"),
            headers={"authorization": f"Bearer {token}", "x-workbench-cli": VERSION},
            params={"limit": 10000},
            timeout=5,
        )
        values = sorted(item[key] for item in response.json()["items"])
    except requests.RequestException, ValueError, KeyError, TypeError:
        return []
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(values))
    return values


def _complete(values, incomplete):
    return [
        CompletionItem(value)
        for value in values
        if value.casefold().startswith(incomplete.casefold())
    ]


def complete_short_names(ctx, param, incomplete):
    return _complete(_completion_values("users", "users/", "short_name"), incomplete)


def complete_internal_types(ctx, param, incomplete):
    return _complete(
        _completion_values("internal-types", "projects/internal-types/", "name"),
        incomplete,
    )


def _complete_teams(ctx, param, incomplete):
    return _complete(_completion_values("teams", "teams/", "name"), incomplete)


def _flatten(row, prefix=""):
    """Nested objects become columns like ``project.code``, lists are joined"""
    result = {}
    for key, value in row.items():
        if isinstance(value, dict):
            result |= _flatten(value, f"{prefix}{key}.")
        elif isinstance(value, list):
            result[f"{prefix}{key}"] = ", ".join(
                json.dumps(item, ensure_ascii=False)
                if isinstance(item, (dict, list))
                else str(item)
                for item in value
            )
        else:
            result[f"{prefix}{key}"] = "" if value is None else value
    return result


def without(row, key):
    return {k: v for k, v in row.items() if k != key}


def echo_csv(rows):
    rows = [_flatten(row) for row in rows]
    writer = csv.DictWriter(
        sys.stdout, fieldnames=list(dict.fromkeys(key for row in rows for key in row))
    )
    writer.writeheader()
    writer.writerows(rows)


def period_options(default):
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


def users_options(fn):
    fn = click.option("--team", help="Team name.", shell_complete=_complete_teams)(fn)
    return click.option(
        "--user",
        "users",
        multiple=True,
        help="Short name, can be repeated.",
        shell_complete=complete_short_names,
    )(fn)


def period_params(period, since, until, *, users=(), team=None):
    params = {"period": period, "user": list(users), "team": team}
    if since:
        params["since"] = since.date().isoformat()
    if until:
        params["until"] = until.date().isoformat()
    return {key: value for key, value in params.items() if value}


def format_number(value, places):
    """Format decimals (strings in the API) and numbers"""
    return f"{float(value):.{places}f}" if value is not None else ""


def format_amount(value):
    return format_number(value, 2)


def format_hours(value):
    return format_number(value, 1)


def format_days(value):
    return format_number(value, 1)


def format_percentage(value):
    return f"{format_number(value, 0)}%" if value is not None else ""


def echo_period(data):
    console.print(f"{data['since']} – {data['until']}", style="bold")


@click.group(cls=_Group)
@click.version_option(VERSION)
@click.option(
    "-i",
    "--installation",
    metavar="NAME",
    expose_value=False,
    callback=_select_installation,
    shell_complete=complete_installations,
    help="Use another installation for this command, any unique part of its URL.",
)
def cli():
    pass


def text_or_stdin(value):
    """Texts given as ``-`` are read from stdin"""
    return sys.stdin.read() if value == "-" else value
