"""Servers hosting sites"""

import click

from wb.core import (
    change_options,
    change_params,
    cli,
    console,
    echo_deleted,
    echo_fields,
    echo_json,
    echo_more,
    format_bool,
    link,
    make_table,
    page_options,
    page_params,
    request,
    terminate,
    text_or_stdin,
)


@cli.group(invoke_without_command=True)
@click.pass_context
def servers(ctx):
    """Servers hosting sites and whom to contact about their outages,
    requires the hosting feature

    Without a command, lists the active servers."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_servers)


@servers.command("list")
@click.option("--include-archived", is_flag=True, help="Also archived servers.")
@page_options
@click.option("--json", "as_json", is_flag=True)
def list_servers(include_archived, limit, offset, as_json):
    """List the servers"""
    data = request(
        "GET",
        "hosting/servers/",
        params={"include_archived": format_bool(include_archived)}
        | page_params(limit, offset),
    )
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Title", "Notes", "Archived")
    for server in data["items"]:
        table.add_row(
            link(server["id"], server["url"]),
            link(server["title"], server["url"]),
            server["notes"].split("\n", 1)[0],
            "yes" if server["is_archived"] else "",
        )
    console.print(table)
    echo_more(data, offset, "servers")


def _echo_server(data):
    echo_fields(
        data["title"],
        [
            ("ID", data["id"]),
            ("Archived", "yes" if data["is_archived"] else ""),
            ("Notes", data["notes"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )


@servers.command("show")
@click.argument("server")
@click.option(
    "--emails", is_flag=True, help="Only the email addresses, comma separated."
)
@click.option("--json", "as_json", is_flag=True)
def show_server(server, emails, as_json):
    """Show a server (ID or title) with the contacts for outages and
    maintenance of its active sites"""
    data = request("GET", f"hosting/servers/{server}/")
    if as_json:
        echo_json(data)
        return
    contacts = data["outage_contacts"]
    if emails:
        click.echo(", ".join(person["email"] for person in contacts if person["email"]))
        return
    _echo_server(data)
    console.print()
    table = make_table("Person", "Organization", "Email", "Phone", "Sites")
    for person in contacts:
        organization = person["organization"]
        table.add_row(
            link(person["full_name"], person["url"]),
            organization["name"] if organization else "",
            person["email"] or "[red]missing[/red]",
            person["phone_number"],
            ", ".join(person["sites"]),
        )
    console.print(table)
    console.print(f"{len(data['sites'])} active sites.", style="dim")


@servers.command("create")
@click.option("--title", required=True)
@click.option("--notes", default="", help="- reads them from stdin.")
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_server(title, notes, dry_run, as_json):
    """Create a server"""
    data = request(
        "POST",
        "hosting/servers/",
        json={"title": title, "notes": text_or_stdin(notes)},
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing created:")
    _echo_server(data)


@servers.command("update")
@click.argument("server")
@click.option("--title")
@click.option(
    "--notes",
    help="Replaces the notes, - reads them from stdin; e.g. how to list the"
    " server's sites.",
)
@click.option("--archived/--not-archived", "is_archived", default=None)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_server(server, title, notes, is_archived, dry_run, as_json):
    """Rename or archive a server (ID or title) or change its notes"""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("notes", text_or_stdin(notes)),
            ("is_archived", is_archived),
        ]
        if value is not None
    }
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"hosting/servers/{server}/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing saved:")
    _echo_server(data)


@servers.command("delete")
@click.argument("server")
@change_options(warnings=False)
def delete_server(server, dry_run, as_json):
    """Delete a server (ID or title), e.g. one created by mistake

    Refused while it has sites, also archived ones; servers which aren't used
    anymore are archived instead (`wb servers update SERVER --archived`)."""
    data = request(
        "DELETE", f"hosting/servers/{server}/", params=change_params(dry_run)
    )
    echo_deleted(
        data, _echo_server, what=data["title"], dry_run=dry_run, as_json=as_json
    )
