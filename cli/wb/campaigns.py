"""Campaigns, which group projects"""

import click

from wb.core import (
    change_options,
    change_params,
    cli,
    complete_short_names,
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


def _echo_campaign(data):
    echo_fields(
        f"{data['code'] or 'New campaign'} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", link(data["customer"]["name"], data["customer"]["url"])),
            ("Owned by", data["owned_by"]),
            ("Description", data["description"]),
        ],
        url=data["url"],
    )


def _echo_saved_campaign(data, *, dry_run, as_json):
    if as_json:
        echo_json(data)
        return
    _echo_campaign(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@campaigns.command("create")
@click.option("--customer", type=int, required=True, help="Organization ID.")
@click.option("--title", required=True)
@click.option("--description", default="", help="The text, or - to read it from stdin.")
@click.option(
    "--owned-by",
    help="Short name, defaults to you.",
    shell_complete=complete_short_names,
)
@change_options()
def create_campaign(
    customer, title, description, owned_by, ignore_warnings, dry_run, as_json
):
    """Create a campaign, which groups projects

    Projects are added to it with `wb projects update ID --campaign ID`."""
    data = {
        "customer": customer,
        "title": title,
        "description": text_or_stdin(description),
    }
    if owned_by:
        data["owned_by"] = owned_by
    data = request(
        "POST",
        "campaigns/",
        params=change_params(dry_run, ignore_warnings),
        json=data,
    )
    _echo_saved_campaign(data, dry_run=dry_run, as_json=as_json)


@campaigns.command("update")
@click.argument("campaign_id", type=int)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--title")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@change_options()
def update_campaign(
    campaign_id,
    customer,
    title,
    description,
    owned_by,
    ignore_warnings,
    dry_run,
    as_json,
):
    """Change a campaign, only the given fields"""
    data = {
        key: value
        for key, value in [
            ("customer", customer),
            ("title", title),
            ("description", text_or_stdin(description)),
            ("owned_by", owned_by),
        ]
        if value is not None
    }
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"campaigns/{campaign_id}/",
        params=change_params(dry_run, ignore_warnings),
        json=data,
    )
    _echo_saved_campaign(data, dry_run=dry_run, as_json=as_json)


@campaigns.command("delete")
@click.argument("campaign_id", type=int)
@change_options()
def delete_campaign(campaign_id, ignore_warnings, dry_run, as_json):
    """Delete a campaign, e.g. one created by mistake

    Its projects stay and are released, which is a warning
    (`--ignore-warning release-projects`)."""
    data = request(
        "DELETE",
        f"campaigns/{campaign_id}/",
        params=change_params(dry_run, ignore_warnings),
    )
    echo_deleted(
        data, _echo_campaign, what=data["code"], dry_run=dry_run, as_json=as_json
    )
