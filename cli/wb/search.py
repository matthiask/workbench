"""Searching everything"""

import click

from wb.core import cli, console, echo_json, link, make_table, request


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option(
    "--limit",
    type=click.IntRange(1, 100),
    default=10,
    show_default=True,
    help="Results per type.",
)
@click.option("--json", "as_json", is_flag=True)
def search(query, limit, as_json):
    """Search projects, contacts, invoices, offers and deals at once

    Like the search field of the web interface. Show results with the
    `show` command of their noun, e.g. `wb projects show ID`."""
    groups = request("GET", "search/", params={"q": " ".join(query), "limit": limit})
    if as_json:
        echo_json(groups)
        return
    groups = [group for group in groups if group["count"]]
    if not groups:
        console.print("No results found.")
        return
    for group in groups:
        title = f"{group['label']} ({group['type']})"
        if group["count"] > len(group["items"]):
            title += f", {len(group['items'])} of {group['count']}"
        table = make_table("ID>", "Title", title=link(title, group["url"]))
        for item in group["items"]:
            table.add_row(link(item["id"], item["url"]), item["title"])
        console.print(table)
