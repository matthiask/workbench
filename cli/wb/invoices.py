"""Invoices, recurring invoices and projected invoices"""

import click
from rich.text import Text

from wb.core import (
    _bool,
    _complete_short_names,
    _echo_csv,
    _echo_fields,
    _echo_invoice_list,
    _echo_json,
    _echo_more,
    _link,
    _page_options,
    _page_params,
    _period_options,
    _period_params,
    _request,
    _table,
    _terminate,
    cli,
    console,
)


@cli.group()
def invoices():
    """Look at invoices"""


@invoices.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option(
    "--status", type=click.Choice(["in_preparation", "sent", "paid", "canceled"])
)
@click.option("--open", "open_", is_flag=True, help="In preparation or sent.")
@click.option("--overdue", is_flag=True, help="Due for more than 15 days.")
@_period_options("filters the invoice date")
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_invoices(
    query,
    project,
    customer,
    status,
    open_,
    overdue,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search invoices, newest first"""
    params = {"q": " ".join(query), "open": _bool(open_), "overdue": _bool(overdue)}
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    if status:
        params["status"] = status
    params |= _period_params(period, since, until)
    data = _request("GET", "invoices/", params=params | _page_params(limit, offset))
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    _echo_invoice_list(data["items"])
    _echo_more(data, offset, "invoices")


@invoices.command("show")
@click.argument("invoice_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_invoice(invoice_id, as_json):
    """Show an invoice"""
    data = _request("GET", f"invoices/{invoice_id}/")
    if as_json:
        _echo_json(data)
        return
    period = (
        f"{data['service_period_from']} – {data['service_period_until']}"
        if data["service_period_from"]
        else None
    )
    _echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Type", data["type"]),
            ("Status", data["status"]),
            ("Customer", _link(data["customer"]["name"], data["customer"]["url"])),
            (
                "Project",
                _link(f"{project['code']} {project['title']}", project["url"])
                if (project := data["project"])
                else None,
            ),
            ("Owned by", data["owned_by"]),
            ("Invoiced on", data["invoiced_on"]),
            ("Due on", data["due_on"]),
            ("Closed on", data["closed_on"]),
            ("Service period", period),
            ("Total excl. tax", data["total_excl_tax"]),
            ("Third party costs", data["third_party_costs"]),
            ("Total", data["total"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["description"]:
        console.print()
        console.print(data["description"])


@invoices.command("reminders")
@click.option("--json", "as_json", is_flag=True)
def invoice_reminders(as_json):
    """Overdue invoices to remind customers of, per customer and contact"""
    data = _request("GET", "invoices/reminders/")
    if as_json:
        _echo_json(data)
    elif data:
        _echo_reminders(data)
    else:
        console.print("No overdue invoices.")


def _echo_reminders(data):
    table = _table(
        "ID>",
        "Code",
        "Title",
        "Invoiced on",
        "Due on",
        "Overdue>",
        "Last reminded on",
        "Total excl. tax>",
    )
    for group in data:
        contact = group["contact"]
        table.add_row(
            "",
            Text.assemble(
                _link(group["customer"]["name"], group["customer"]["url"]),
                " / ",
                _link(contact["full_name"], contact["url"])
                if contact
                else "(contact missing)",
                style="bold",
            ),
            "",
            "",
            "",
            "",
            "",
            group["total_excl_tax"],
            style="bold",
        )
        for invoice in group["invoices"]:
            table.add_row(
                _link(invoice["id"], invoice["url"]),
                _link(invoice["code"], invoice["url"]),
                invoice["title"],
                invoice["invoiced_on"],
                invoice["due_on"],
                f"{invoice['days_overdue']} days",
                invoice["last_reminded_on"] or "",
                invoice["total_excl_tax"],
            )
    console.print(table)


@invoices.command("postpone-reminders")
@click.argument("invoice_id", type=int)
@click.argument("until", type=click.DateTime(formats=["%Y-%m-%d"]), required=False)
@click.option("--clear", is_flag=True, help="Don't postpone reminders anymore.")
@click.option(
    "--confirm", is_flag=True, help="Postpone by more than 30 days (at most 60)."
)
@click.option("--json", "as_json", is_flag=True)
def postpone_reminders(invoice_id, until, clear, confirm, as_json):
    """Leave a sent invoice out of the reminders until a date, e.g. while a
    question of the customer is being clarified"""
    if bool(until) == clear:
        _terminate("Pass either a date or --clear.")
    data = _request(
        "POST",
        f"invoices/{invoice_id}/postpone-reminders/",
        json={
            "until": until.date().isoformat() if until else None,
            "confirm": confirm,
        },
    )
    if as_json:
        _echo_json(data)
    elif data["postpone_reminders_until"]:
        console.print(
            f"Reminders of {data['code']} are postponed until"
            f" {data['postpone_reminders_until']}."
        )
    else:
        console.print(f"Reminders of {data['code']} aren't postponed anymore.")


@invoices.command("mark-reminded")
@click.argument("invoice_ids", type=int, nargs=-1, required=True)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def mark_reminded(invoice_ids, dry_run, as_json):
    """Mark overdue invoices as reminded today, e.g. after sending a dunning
    letter"""
    data = _request(
        "POST",
        "invoices/reminders/",
        params={"dry_run": _bool(dry_run)},
        json={"invoices": list(invoice_ids)},
    )
    if as_json:
        _echo_json(data)
        return
    _echo_reminders(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@cli.group("recurring-invoices")
def recurring_invoices():
    """Look at recurring invoices, requires the controlling feature"""


@recurring_invoices.command("search")
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=_complete_short_names)
@click.option(
    "--status",
    type=click.Choice(["open", "closed", "all"]),
    default="open",
    help="Open ones are those which still renew, the default.",
)
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_recurring_invoices(
    query, customer, owned_by, status, limit, offset, as_csv, as_json
):
    """Search recurring invoices, by customer"""
    params = {"q": " ".join(query), "status": status}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = _request(
        "GET", "recurring-invoices/", params=params | _page_params(limit, offset)
    )
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    table = _table(
        "ID>",
        "Title",
        "Customer",
        "Owned by",
        "Periodicity",
        "Next period",
        "Ends on",
        "Total excl. tax>",
    )
    for invoice in data["items"]:
        table.add_row(
            _link(invoice["id"], invoice["url"]),
            _link(invoice["title"], invoice["url"]),
            _link(invoice["customer"]["name"], invoice["customer"]["url"]),
            invoice["owned_by"],
            invoice["periodicity"],
            invoice["next_period_starts_on"] or invoice["starts_on"],
            invoice["ends_on"] or "",
            invoice["total_excl_tax"],
        )
    console.print(table)
    _echo_more(data, offset, "recurring invoices")


@cli.group("projected-invoices")
def projected_invoices():
    """Look at the planned invoicing"""


@projected_invoices.command("search")
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@_period_options("filters the planned invoice date")
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_projected_invoices(
    project, customer, period, since, until, limit, offset, as_csv, as_json
):
    """Search the planned invoicing (gross margin), oldest first"""
    params = _period_params(period, since, until)
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    data = _request(
        "GET", "projected-invoices/", params=params | _page_params(limit, offset)
    )
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    table = _table("Project", "Invoiced on", "Gross margin>", "Description")
    for row in data["items"]:
        table.add_row(
            _link(row["project"]["code"], row["project"]["url"]),
            row["invoiced_on"],
            row["gross_margin"],
            row["description"],
        )
    console.print(table)
    _echo_more(data, offset, "projected invoices")
