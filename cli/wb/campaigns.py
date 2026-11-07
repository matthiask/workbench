"""Campaigns, which group projects"""

import click

from wb.core import (
    cli,
    complete_short_names,
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


@cli.group(invoke_without_command=True)
@click.pass_context
def campaigns(ctx):
    """Find campaigns, e.g. for `wb planning export --campaign`

    Without a command, lists the campaigns with open projects."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_campaigns)


@campaigns.command("search")
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option(
    "--include-closed", is_flag=True, help="Also campaigns without open projects."
)
@page_options
@click.option("--json", "as_json", is_flag=True)
def search_campaigns(query, customer, owned_by, include_closed, limit, offset, as_json):
    """Search campaigns, those with open projects by default"""
    params = {
        "q": " ".join(query),
        "include_closed": format_bool(include_closed),
    }
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = request("GET", "campaigns/", params=params | page_params(limit, offset))
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Code", "Title", "Customer", "Owned by")
    for campaign in data["items"]:
        table.add_row(
            link(campaign["id"], campaign["url"]),
            link(campaign["code"], campaign["url"]),
            campaign["title"],
            link(campaign["customer"]["name"], campaign["customer"]["url"]),
            campaign["owned_by"],
        )
    console.print(table)
    echo_more(data, offset, "campaigns")
