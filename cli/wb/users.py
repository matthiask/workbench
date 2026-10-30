"""Users and teams"""

import click

from wb.core import (
    cli,
    console,
    echo_json,
    echo_more,
    format_bool,
    link,
    make_table,
    page_options,
    page_params,
    request,
)


@cli.group()
def users():
    """Find users and their short names"""


@users.command("search")
@click.argument("query", nargs=-1)
@click.option("--all", "include_inactive", is_flag=True, help="Include inactive.")
@page_options
@click.option("--json", "as_json", is_flag=True)
def search_users(query, include_inactive, limit, offset, as_json):
    """Search users by name, short name or email address, active users by
    default"""
    params = {"q": " ".join(query), "include_inactive": format_bool(include_inactive)}
    data = request("GET", "users/", params=params | page_params(limit, offset))
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Short name", "Name", "Email", "Teams")
    for user in data["items"]:
        table.add_row(
            link(user["id"], user["url"]),
            user["short_name"],
            link(user["full_name"], user["url"])
            + ("" if user["is_active"] else " (inactive)"),
            user["email"],
            ", ".join(user["teams"]),
        )
    console.print(table)
    echo_more(data, offset, "users")


@cli.group()
def teams():
    """Find teams and their members, e.g. for the --team option"""


@teams.command("search")
@click.argument("query", nargs=-1)
@page_options
@click.option("--json", "as_json", is_flag=True)
def search_teams(query, limit, offset, as_json):
    """Search teams by name"""
    data = request(
        "GET",
        "teams/",
        params={"q": " ".join(query)} | page_params(limit, offset),
    )
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Name", "Members")
    for team in data["items"]:
        table.add_row(
            link(team["id"], team["url"]),
            link(team["name"], team["url"]),
            ", ".join(team["members"]),
        )
    console.print(table)
    echo_more(data, offset, "teams")
