"""Users and teams"""

import click

from wb.core import (
    _bool,
    _echo_json,
    _echo_more,
    _link,
    _page_options,
    _page_params,
    _request,
    _table,
    cli,
    console,
)


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
def teams():
    """Find teams and their members, e.g. for the --team option"""


@teams.command("search")
@click.argument("query", nargs=-1)
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_teams(query, limit, offset, as_json):
    """Search teams by name"""
    data = _request(
        "GET",
        "teams/",
        params={"q": " ".join(query)} | _page_params(limit, offset),
    )
    if as_json:
        _echo_json(data)
        return
    table = _table("ID>", "Name", "Members")
    for team in data["items"]:
        table.add_row(
            _link(team["id"], team["url"]),
            _link(team["name"], team["url"]),
            ", ".join(team["members"]),
        )
    console.print(table)
    _echo_more(data, offset, "teams")
