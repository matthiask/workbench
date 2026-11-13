"""Invoices, recurring invoices and projected invoices"""

import click
from rich.text import Text

from wb.core import (
    cli,
    complete_short_names,
    console,
    download,
    echo_actionable,
    echo_csv,
    echo_fields,
    echo_invoice_list,
    echo_json,
    echo_more,
    format_bool,
    ignore_warnings_option,
    link,
    make_table,
    page_options,
    page_params,
    period_options,
    period_params,
    request,
    terminate,
    text_or_stdin,
)


@cli.group(invoke_without_command=True)
@click.pass_context
def invoices(ctx):
    """Look at invoices and create drafts

    Without a command, lists your invoices which may need action."""
    if ctx.invoked_subcommand is None:
        echo_actionable("invoices", "controlling")


@invoices.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option(
    "--type",
    "type_",
    type=click.Choice(["fixed", "down-payment", "services", "credit"]),
)
@click.option(
    "--status", type=click.Choice(["in_preparation", "sent", "paid", "canceled"])
)
@click.option("--open", "open_", is_flag=True, help="In preparation or sent.")
@click.option("--overdue", is_flag=True, help="Due for more than 15 days.")
@period_options("filters the invoice date")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_invoices(
    query,
    project,
    customer,
    owned_by,
    type_,
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
    params = {
        "q": " ".join(query),
        "open": format_bool(open_),
        "overdue": format_bool(overdue),
    }
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    if type_:
        params["type"] = type_
    if status:
        params["status"] = status
    params |= period_params(period, since, until)
    data = request("GET", "invoices/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    echo_invoice_list(data["items"])
    echo_more(data, offset, "invoices")


@invoices.command("show")
@click.argument("invoice_id")
@click.option("--json", "as_json", is_flag=True)
def show_invoice(invoice_id, as_json):
    """Show an invoice, by ID or code (2026-0042-0001, 00042 without project)"""
    data = request("GET", f"invoices/{invoice_id}/")
    if as_json:
        echo_json(data)
        return
    _echo_invoice(data)


def _echo_invoice(data):
    period = (
        f"{data['service_period_from']} – {data['service_period_until']}"
        if data["service_period_from"]
        else None
    )
    echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Type", data["type_label"]),
            ("Status", data["status_label"]),
            ("Customer", link(data["customer"]["name"], data["customer"]["url"])),
            (
                "Project",
                link(f"{project['code']} {project['title']}", project["url"])
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
    if data.get("services"):
        table = make_table(
            "Service",
            "Project service>",
            "Offer",
            "Effort type",
            "Hours>",
            "Rate>",
            "Cost>",
        )
        for service in data["services"]:
            table.add_row(
                service["title"],
                str(service["project_service_id"] or ""),
                service["offer"] or "",
                service["effort_type"],
                service["effort_hours"] or "",
                service["effort_rate"] or "",
                service["service_cost"],
            )
        console.print()
        console.print(table)


@invoices.command("pdf")
@click.argument("invoice_id")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    help="File or directory, defaults to the invoice's file name here.",
)
def invoice_pdf(invoice_id, output):
    """Save the PDF of an invoice, by ID or code"""
    download(f"invoices/{invoice_id}/pdf/", output)


SOURCES = ("offer", "logbook", "surplus")


def _parse_services(_ctx, _param, values):
    services = []
    for value in values:
        id, _sep, source = value.partition(":")
        if not id.isdigit() or (source and source not in SOURCES):
            raise click.BadParameter(
                f"{value!r} isn't an ID, optionally followed by :" + ", :".join(SOURCES)
            )
        services.append((int(id), source or None))
    return services


@invoices.command("create")
@click.option("--project", type=int, help="Project ID.")
@click.option(
    "--offer",
    type=int,
    help="Offer ID: invoice its services, with its title and description.",
)
@click.option(
    "--contact",
    type=int,
    help="Person ID, defaults to the project's contact. Required without project.",
)
@click.option(
    "--type",
    "type_",
    type=click.Choice(["fixed", "down-payment", "services", "credit"]),
    help="Defaults to services with --offer or --service, else fixed.",
)
@click.option(
    "--service",
    "services",
    multiple=True,
    callback=_parse_services,
    metavar="ID[:SOURCE]",
    help="ID of a service to invoice, defaults to the offer's services with"
    " something to invoice. How it's invoiced after a colon: offer, logbook"
    " or surplus (the work logged beyond what has been invoiced, after"
    " invoicing the offer), e.g. 42:logbook; defaults to the surplus after"
    " invoicing the offer, the logbook after invoicing the logbook, and the"
    " offer if something has been offered.",
)
@click.option(
    "--disable-logging",
    type=int,
    multiple=True,
    metavar="ID",
    help="ID of an invoiced service on which logging is disabled afterwards.",
)
@click.option(
    "--logbook-cutoff-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Only logged work up to this date.",
)
@click.option(
    "--down-payment",
    "down_payments",
    type=int,
    multiple=True,
    help="ID of a sent or paid down payment invoice of the project to deduct.",
)
@click.option("--title", help="Defaults to the project's (and the offer's).")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option(
    "--subtotal",
    type=float,
    help="Fixed amount, down payment and credit invoices, excl. tax.",
)
@click.option("--third-party-costs", type=float)
@click.option("--discount", type=float, help="Amount excl. tax.")
@click.option("--vat/--no-vat", "liable_to_vat", default=True, show_default=True)
@click.option("--tax-rate", type=float, help="Defaults to the current tax rate.")
@click.option("--service-period-from", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--service-period-until", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option(
    "--postal-address",
    help="Defaults to the billing address of the contact or the customer.",
)
@click.option(
    "--owned-by",
    help="Short name, defaults to you.",
    shell_complete=complete_short_names,
)
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_invoice(
    project,
    offer,
    contact,
    type_,
    services,
    disable_logging,
    down_payments,
    logbook_cutoff_date,
    title,
    description,
    subtotal,
    third_party_costs,
    discount,
    liable_to_vat,
    tax_rate,
    service_period_from,
    service_period_until,
    postal_address,
    owned_by,
    ignore_warnings,
    dry_run,
    as_json,
):
    """Create an invoice in preparation, to be checked and sent in the web
    interface

    Invoice an offer (--offer), selected services of a project (--service,
    as offered, as logged or the surplus), a fixed amount, down payment or
    credit of a project (--project --subtotal) or a fixed amount for a
    contact without project (--contact --title --subtotal)."""
    data = {
        key: value
        for key, value in [
            ("project", project),
            ("offer", offer),
            ("contact", contact),
            ("type", type_),
            ("title", title),
            ("description", text_or_stdin(description)),
            ("subtotal", subtotal),
            ("third_party_costs", third_party_costs),
            ("discount", discount),
            ("tax_rate", tax_rate),
            ("postal_address", postal_address),
            ("owned_by", owned_by),
        ]
        if value is not None
    }
    data["liable_to_vat"] = liable_to_vat
    if services:
        data["services"] = [id for id, _source in services]
        if sources := {id: source for id, source in services if source}:
            data["sources"] = sources
    if disable_logging:
        data["disable_logging"] = list(disable_logging)
    if down_payments:
        data["down_payments"] = list(down_payments)
    for key, value in [
        ("logbook_cutoff_date", logbook_cutoff_date),
        ("service_period_from", service_period_from),
        ("service_period_until", service_period_until),
    ]:
        if value:
            data[key] = value.date().isoformat()
    data = request(
        "POST",
        "invoices/",
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
        json=data,
    )
    if as_json:
        echo_json(data)
        return
    if data["id"]:
        _echo_invoice(data)
    else:
        console.print(
            f"{data['title']}: {data['total_excl_tax']} excl. tax"
            f" ({len(data['services'])} services)"
        )
        console.print("Dry run, nothing has been saved.")


@invoices.command("reminders")
@click.option("--json", "as_json", is_flag=True)
def invoice_reminders(as_json):
    """Overdue invoices to remind customers of, per customer and contact"""
    data = request("GET", "invoices/reminders/")
    if as_json:
        echo_json(data)
    elif data:
        _echo_reminders(data)
    else:
        console.print("No overdue invoices.")


def _echo_reminders(data):
    table = make_table(
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
                link(group["customer"]["name"], group["customer"]["url"]),
                " / ",
                link(contact["full_name"], contact["url"])
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
                link(invoice["id"], invoice["url"]),
                link(invoice["code"], invoice["url"]),
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
        terminate("Pass either a date or --clear.")
    data = request(
        "POST",
        f"invoices/{invoice_id}/postpone-reminders/",
        json={
            "until": until.date().isoformat() if until else None,
            "confirm": confirm,
        },
    )
    if as_json:
        echo_json(data)
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
    data = request(
        "POST",
        "invoices/reminders/",
        params={"dry_run": format_bool(dry_run)},
        json={"invoices": list(invoice_ids)},
    )
    if as_json:
        echo_json(data)
        return
    _echo_reminders(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@invoices.command("send-reminder")
@click.argument("contact_id", type=int)
@click.option("--to", help="Recipient, e.g. one of the contact's email addresses.")
@click.option("--dry-run", is_flag=True, help="Show what would be sent only.")
@click.option("--json", "as_json", is_flag=True)
def send_reminder(contact_id, to, dry_run, as_json):
    """Send a dunning letter with the overdue invoices of a contact

    Without --to, shows the contact's email addresses and the invoices
    without sending anything. The owners of the invoices and you get a copy,
    the invoices are marked as reminded today. Requires the bookkeeping
    feature."""
    data = request(
        "POST",
        f"invoices/reminders/{contact_id}/send/",
        params={"dry_run": format_bool(dry_run)},
        json={"to": to},
    )
    if as_json:
        echo_json(data)
        return
    contact = data["contact"]
    echo_fields(
        contact["full_name"],
        [
            ("Email addresses", ", ".join(data["emails"]) or "(none)"),
            ("To", ", ".join(data["to"])),
            ("Cc", ", ".join(data["cc"])),
            ("Bcc", ", ".join(data["bcc"])),
        ],
        url=contact["url"],
    )
    echo_invoice_list(data["invoices"], title="Overdue invoices")
    if data["sent"]:
        console.print("The reminder has been sent.")
    elif not to:
        console.print("Nothing sent, choose a recipient with --to.")
    else:
        console.print("Dry run, nothing has been sent.")


@cli.group("recurring-invoices", invoke_without_command=True)
@click.pass_context
def recurring_invoices(ctx):
    """Look at recurring invoices, requires the controlling feature

    Without a command, lists the open ones."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_recurring_invoices)


@recurring_invoices.command("search")
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option(
    "--include-closed",
    is_flag=True,
    help="Also those which don't renew anymore.",
)
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_recurring_invoices(
    query, customer, owned_by, include_closed, limit, offset, as_csv, as_json
):
    """Search recurring invoices which still renew, by customer"""
    params = {"q": " ".join(query), "include_closed": format_bool(include_closed)}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = request(
        "GET", "recurring-invoices/", params=params | page_params(limit, offset)
    )
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
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
            link(invoice["id"], invoice["url"]),
            link(invoice["title"], invoice["url"]),
            link(invoice["customer"]["name"], invoice["customer"]["url"]),
            invoice["owned_by"],
            invoice["periodicity_label"],
            invoice["next_period_starts_on"] or invoice["starts_on"],
            invoice["ends_on"] or "",
            invoice["total_excl_tax"],
        )
    console.print(table)
    echo_more(data, offset, "recurring invoices")


@cli.group("projected-invoices", invoke_without_command=True)
@click.pass_context
def projected_invoices(ctx):
    """Look at the planned invoicing

    Without a command, lists all of them."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_projected_invoices)


@projected_invoices.command("search")
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@period_options("filters the planned invoice date")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_projected_invoices(
    project, customer, period, since, until, limit, offset, as_csv, as_json
):
    """Search the planned invoicing (gross margin), oldest first"""
    params = period_params(period, since, until)
    if project:
        params["project"] = project
    if customer:
        params["customer"] = customer
    data = request(
        "GET", "projected-invoices/", params=params | page_params(limit, offset)
    )
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table("Project", "Invoiced on", "Gross margin>", "Description")
    for row in data["items"]:
        table.add_row(
            link(row["project"]["code"], row["project"]["url"]),
            row["invoiced_on"],
            row["gross_margin"],
            row["description"],
        )
    console.print(table)
    echo_more(data, offset, "projected invoices")
