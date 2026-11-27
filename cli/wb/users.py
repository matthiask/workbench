"""Users and teams"""

from urllib.parse import quote

import click

from wb.core import (
    change_options,
    change_params,
    cli,
    complete_short_names,
    console,
    echo_deleted,
    echo_json,
    echo_more,
    forget_completion_values,
    format_bool,
    link,
    make_table,
    page_options,
    page_params,
    request,
    terminate,
)


@cli.group(invoke_without_command=True)
@click.pass_context
def users(ctx):
    """Find users and their short names

    Without a command, lists the active users."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_users)


@users.command("search")
@click.argument("query", nargs=-1)
@click.option("--include-inactive", is_flag=True, help="Also inactive users.")
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


@cli.group(invoke_without_command=True)
@click.pass_context
def teams(ctx):
    """Find teams and their members, e.g. for the --team option

    Without a command, lists all teams."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_teams)


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


def _echo_team(team):
    console.print(f"[bold]{link(team['name'], team['url'])}[/bold] (ID {team['id']})")
    console.print(f"Members: {', '.join(team['members'])}")


def _team_path(team):
    return f"teams/{quote(team, safe='')}/"


def _echo_changed_team(data, *, dry_run, as_json):
    if not dry_run:
        # The names are cached for completing --team
        forget_completion_values("teams")
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing saved:")
    _echo_team(data)


@teams.command("create")
@click.argument("name")
@click.option(
    "--member",
    "members",
    multiple=True,
    required=True,
    help="Short name of an active user; repeat it for several.",
    shell_complete=complete_short_names,
)
@change_options(warnings=False)
def create_team(name, members, dry_run, as_json):
    """Create a team, e.g. for the --team option of reports and the
    planning"""
    data = request(
        "POST",
        "teams/",
        json={"name": name, "members": list(members)},
        params=change_params(dry_run),
    )
    _echo_changed_team(data, dry_run=dry_run, as_json=as_json)


@teams.command("update")
@click.argument("team")
@click.option("--name", help="Renames the team.")
@click.option(
    "--member",
    "members",
    multiple=True,
    help="Replaces the members: short name of an active user; repeat it for several.",
    shell_complete=complete_short_names,
)
@click.option(
    "--add-member",
    "add_members",
    multiple=True,
    help="Short name of an active user; repeat it for several.",
    shell_complete=complete_short_names,
)
@click.option(
    "--remove-member",
    "remove_members",
    multiple=True,
    help="Short name; repeat it for several.",
    shell_complete=complete_short_names,
)
@change_options(warnings=False)
def update_team(team, name, members, add_members, remove_members, dry_run, as_json):
    """Rename a team (ID or name) or change its members

    Members who left are dropped, like in the web interface."""
    data = {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in [
            ("name", name),
            ("members", members or None),
            ("add_members", add_members),
            ("remove_members", remove_members),
        ]
        if value
    }
    if not data:
        terminate("Nothing to change.")
    data = request("PATCH", _team_path(team), json=data, params=change_params(dry_run))
    _echo_changed_team(data, dry_run=dry_run, as_json=as_json)


@teams.command("delete")
@click.argument("team")
@change_options(warnings=False)
def delete_team(team, dry_run, as_json):
    """Delete a team (ID or name); its members stay"""
    data = request("DELETE", _team_path(team), params=change_params(dry_run))
    if not dry_run:
        forget_completion_values("teams")
    echo_deleted(data, _echo_team, what=data["name"], dry_run=dry_run, as_json=as_json)
