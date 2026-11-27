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


NEW_INVOICES = ["prepare", "mark_as_sent", "send"]


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
            (
                "Recurring invoice",
                link(recurring["title"], recurring["url"])
                if (recurring := data.get("recurring_invoice"))
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


SOURCES = ("offer", "logbook")


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
    " something to invoice. How it's invoiced after a colon: offer or logbook"
    " (the work which hasn't been invoiced yet, after invoicing the offer"
    " the surplus), e.g. 42:logbook; defaults to the offer for services with"
    " something offered which haven't been invoiced, else to the logbook.",
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
    as offered or as logged), a fixed amount, down payment or
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
    "--new-invoices",
    type=click.Choice(NEW_INVOICES),
    help="Only those creating new invoices this way.",
)
@click.option(
    "--include-closed",
    is_flag=True,
    help="Also those which don't renew anymore.",
)
@click.option("--site", type=int, help="ID of the hosted site.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_recurring_invoices(
    query,
    customer,
    owned_by,
    new_invoices,
    include_closed,
    site,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search recurring invoices which still renew, by customer"""
    params = {"q": " ".join(query), "include_closed": format_bool(include_closed)}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    if new_invoices:
        params["new_invoices"] = new_invoices
    if site:
        params["site"] = site
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
        "New invoices",
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
            invoice["send_to"]
            if invoice["new_invoices"] == "send"
            else invoice["new_invoices_label"],
        )
    console.print(table)
    echo_more(data, offset, "recurring invoices")


@recurring_invoices.command("show")
@click.argument("invoice_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_recurring_invoice(invoice_id, as_json):
    """Show a recurring invoice with how its new invoices are sent"""
    data = request("GET", f"recurring-invoices/{invoice_id}/")
    if as_json:
        echo_json(data)
        return
    _echo_recurring_invoice(data)


def _echo_recurring_invoice(data):
    contact = data["contact"]
    sending = data["new_invoices"] == "send"
    echo_fields(
        data["title"],
        [
            ("ID", data["id"]),
            ("Customer", link(data["customer"]["name"], data["customer"]["url"])),
            ("Contact", contact and link(contact["full_name"], contact["url"])),
            (
                "Site",
                data["site"] and f"{data['site']['title']} ({data['site']['id']})",
            ),
            ("Owned by", data["owned_by"]),
            ("Periodicity", data["periodicity_label"]),
            ("Starts on", data["starts_on"]),
            ("Ends on", data["ends_on"]),
            ("Next period", data["next_period_starts_on"]),
            ("Total excl. tax", data["total_excl_tax"]),
            ("Third party costs", data["third_party_costs"]),
            ("New invoices", data["new_invoices_label"]),
            ("Recipient", data["send_to"] if sending else None),
            ("Subject", data["mail_subject"] if sending else None),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["description"]:
        console.print()
        console.print(data["description"])
    if sending and data["mail_body"]:
        console.print()
        console.print(Text(data["mail_body"]))


@recurring_invoices.command("update")
@click.argument("invoice_id", type=int)
@click.option("--title", help="Also the title of the invoices created.")
@click.option(
    "--description",
    help="Also the description of the invoices created, or - to read it from stdin.",
)
@click.option(
    "--owned-by",
    help="Short name, also responsible for the invoices created.",
    shell_complete=complete_short_names,
)
@click.option(
    "--new-invoices",
    type=click.Choice(NEW_INVOICES),
    help="Create them in preparation, mark them as sent or send them by email"
    " automatically.",
)
@click.option(
    "--send-to",
    help="The recipient when sending by email, an empty value proposes one"
    " (like the subject and the text).",
)
@click.option("--mail-subject")
@click.option(
    "--mail-body",
    help="The text, or - to read it from stdin; {code}, {total}, {due_on} and"
    " {service_period} are replaced with the values of each invoice.",
)
@click.option("--site", type=int, help="ID of the hosted site (of the same customer).")
@click.option("--no-site", is_flag=True, help="Remove the site.")
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_recurring_invoice(
    invoice_id,
    title,
    description,
    owned_by,
    new_invoices,
    send_to,
    mail_subject,
    mail_body,
    site,
    no_site,
    ignore_warnings,
    dry_run,
    as_json,
):
    """Change the title, description, site and responsible person of new
    invoices and how they are created and sent, only the given fields"""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", text_or_stdin(description)),
            ("owned_by", owned_by),
            ("new_invoices", new_invoices),
            ("send_to", send_to),
            ("mail_subject", mail_subject),
            ("mail_body", text_or_stdin(mail_body)),
            ("site", site),
        ]
        if value is not None
    }
    if no_site:
        data["site"] = None
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"recurring-invoices/{invoice_id}/",
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
        json=data,
    )
    if as_json:
        echo_json(data)
        return
    _echo_recurring_invoice(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


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
