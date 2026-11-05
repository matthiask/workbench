"""Offers and their services"""

from pathlib import Path

import click

from wb import core
from wb.core import (
    announce_installation,
    cli,
    complete_short_names,
    current_installation,
    echo_actionable,
    echo_csv,
    echo_json,
    echo_more,
    echo_offer,
    echo_offer_list,
    format_bool,
    format_error,
    load,
    page_options,
    page_params,
    period_options,
    period_params,
    read_config,
    request,
    terminate,
    text_or_stdin,
    write_config,
)


@cli.group(invoke_without_command=True)
@click.pass_context
def offers(ctx):
    """Create and update offers

    Without a command, lists your offers which may need action."""
    if ctx.invoked_subcommand is None:
        echo_actionable("offers", "controlling")


@offers.command()
@click.argument("project_id", type=int)
def context(project_id):
    """Print the project, its offers, service types and the offer schema

    Feed this to an LLM together with the specification of the offer."""
    echo_json(request("GET", f"projects/{project_id}/offers/context/"))


@offers.command()
@click.option(
    "--set",
    "path",
    type=click.Path(path_type=Path),
    help="Use this file for the current installation.",
)
@click.option("--clear", is_flag=True, help="Stop using a file.")
def guidelines(path, clear):
    """Print the private offer guidelines of the current installation

    Guidelines (rules, benchmarks from past projects) often contain
    confidential figures, so they are kept in a file of your own instead of
    in Workbench. Configure it once with --set PATH."""
    url = current_installation()
    announce_installation(url)
    if path or clear:
        config = read_config()
        if url not in config["installations"]:
            terminate("Not configured yet. Run `wb login URL` first.")
        installation = config["installations"][url]
        if clear:
            installation.pop("offer_guidelines", None)
        else:
            path = path.expanduser().resolve()
            if not path.is_file():
                terminate(f"{path} does not exist.")
            installation["offer_guidelines"] = str(path)
        write_config(config)
        click.echo(f"Saved {core.CONFIG}", err=True)
        return
    configured = read_config()["installations"].get(url, {}).get("offer_guidelines")
    if not configured:
        click.echo(
            f"No offer guidelines configured for {url}."
            " Use `wb offers guidelines --set PATH` to add your own.",
            err=True,
        )
        return
    if not Path(configured).is_file():
        terminate(f"{configured} does not exist.")
    click.echo(f"Offer guidelines for {url} from {configured}", err=True)
    click.echo(Path(configured).read_text(encoding="utf-8"), nl=False)


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
        "discarded",
    ]),
)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--external-reference", help="Exact match of one of the URLs.")
@period_options("filters the offer date")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_offers(
    query,
    status,
    project,
    customer,
    owned_by,
    external_reference,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
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
    if external_reference:
        params["external_reference"] = external_reference
    params |= period_params(period, since, until)
    data = request("GET", "offers/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    echo_offer_list(data["items"])
    echo_more(data, offset, "offers")


@offers.command()
@click.argument("offer_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show(offer_id, as_json):
    """Show an offer"""
    data = request("GET", f"offers/{offer_id}/")
    echo_json(data) if as_json else echo_offer(data)


@offers.command()
@click.argument("project_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def create(project_id, file, dry_run, as_json):
    """Create an offer in preparation from a YAML or JSON file"""
    data = request(
        "POST",
        f"projects/{project_id}/offers/",
        params={"dry_run": format_bool(dry_run)},
        json=load(file),
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
    `wb services` change parts of it."""
    data = request(
        "PUT",
        f"offers/{offer_id}/",
        params={"dry_run": format_bool(dry_run)},
        json=load(file),
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)


def _echo_changed_offer(data, *, dry_run, as_json):
    if as_json:
        echo_json(data)
        return
    echo_offer(data)
    for warning in data["warnings"]:
        click.secho(f"Warning: {format_error(warning)}", fg="yellow", err=True)
    if dry_run:
        click.secho("Dry run, nothing has been saved.", fg="yellow", err=True)


@offers.command("update")
@click.argument("offer_id", type=int)
@click.option("--title")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option(
    "--discount", type=float, help="Amount excl. tax, 0 removes the discount."
)
@click.option(
    "--external-reference",
    multiple=True,
    help="URL, e.g. of an issue; repeat it for several. Replaces the existing"
    ' ones, "" removes them.',
)
@click.option("--dry-run", is_flag=True, help="Validate and show totals only.")
@click.option("--json", "as_json", is_flag=True)
def update_offer(
    offer_id, title, description, discount, external_reference, dry_run, as_json
):
    """Change the title, the description or the discount of an offer in
    preparation, or the external references of any offer"""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", text_or_stdin(description)),
            ("discount", discount),
            (
                "external_reference",
                "\n".join(external_reference) if external_reference else None,
            ),
        ]
        if value is not None
    }
    if not data:
        terminate(
            "Nothing to change, pass --title, --description, --discount"
            " or --external-reference."
        )
    data = request(
        "PATCH",
        f"offers/{offer_id}/",
        params={"dry_run": format_bool(dry_run)},
        json=data,
    )
    _echo_changed_offer(data, dry_run=dry_run, as_json=as_json)
