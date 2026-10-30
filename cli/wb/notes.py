"""Notes"""

import click

from wb.core import (
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_json,
    echo_more,
    link,
    page_options,
    page_params,
    period_options,
    period_params,
    request,
)


@cli.group()
def notes():
    """Search and add notes on deals and invoices"""


def _echo_notes(notes):
    for note in notes:
        obj = note["object"]
        console.print(
            link(f"{obj['name']} ({obj['type']} {obj['id']})", obj["url"]),
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
@click.option("--created-by", help="Short name.", shell_complete=complete_short_names)
@period_options("filters the creation date")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
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
    as_csv,
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
    params |= period_params(period, since, until)
    data = request("GET", "notes/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
    elif data["items"]:
        _echo_notes(data["items"])
        echo_more(data, offset, "notes")
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
    data = request(
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
    echo_json(data) if as_json else _echo_notes([data])
