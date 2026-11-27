"""Notes"""

import click

from wb.core import (
    change_options,
    change_params,
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_deleted,
    echo_json,
    echo_more,
    link,
    page_options,
    page_params,
    period_options,
    period_params,
    request,
    terminate,
    text_or_stdin,
)


@cli.group()
def notes():
    """Search, add, change and delete notes on deals, invoices and projects"""


def _echo_note(note):
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


def _echo_notes(notes):
    for note in notes:
        _echo_note(note)
        console.print()


@notes.command("search")
@click.argument("query", nargs=-1)
@click.option("--deal", type=int, help="Deal ID.")
@click.option("--invoice", type=int, help="Invoice ID.")
@click.option("--recurring-invoice", type=int, help="Recurring invoice ID.")
@click.option("--project", type=int, help="Project ID.")
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
    project,
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
        ("project", project),
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
@click.option("--project", type=int, help="Project ID.")
@click.option("--title", required=True)
@click.option("--description", required=True, help="- reads it from stdin.")
@click.option("--json", "as_json", is_flag=True)
def create_note(deal, invoice, recurring_invoice, project, title, description, as_json):
    """Add a note to exactly one deal, invoice, recurring invoice or project

    Like in Workbench, the owner of the object finds it in the daily notes
    digest mail."""
    data = request(
        "POST",
        "notes/",
        json={
            "title": title,
            "description": text_or_stdin(description),
            "deal": deal,
            "invoice": invoice,
            "recurring_invoice": recurring_invoice,
            "project": project,
        },
    )
    echo_json(data) if as_json else _echo_notes([data])


@notes.command("show")
@click.argument("note_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_note(note_id, as_json):
    """Show a note with its object"""
    data = request("GET", f"notes/{note_id}/")
    echo_json(data) if as_json else _echo_note(data)


@notes.command("update")
@click.argument("note_id", type=int)
@click.option("--title")
@click.option("--description", help="- reads it from stdin.")
@change_options(warnings=False)
def update_note(note_id, title, description, dry_run, as_json):
    """Change the title or the description of a note, also of notes others
    wrote, like in Workbench

    Notes stay on their object. The owner of the object finds the change in
    the daily notes digest mail."""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", text_or_stdin(description)),
        ]
        if value is not None
    }
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH", f"notes/{note_id}/", params=change_params(dry_run), json=data
    )
    if as_json:
        echo_json(data)
        return
    _echo_note(data)
    if dry_run:
        console.print()
        console.print("Dry run, nothing has been saved.")


@notes.command("delete")
@click.argument("note_id", type=int)
@change_options(warnings=False)
def delete_note(note_id, dry_run, as_json):
    """Delete a note, also notes others wrote, like in Workbench"""
    data = request("DELETE", f"notes/{note_id}/", params=change_params(dry_run))
    echo_deleted(
        data,
        _echo_note,
        what=f"note {data['title']}",
        dry_run=dry_run,
        as_json=as_json,
    )
