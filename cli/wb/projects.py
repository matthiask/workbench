"""Projects"""

import datetime as dt

import click

from wb.core import (
    change_options,
    change_params,
    cli,
    complete_internal_types,
    complete_short_names,
    console,
    deal_links,
    echo_csv,
    echo_deleted,
    echo_fields,
    echo_json,
    echo_more,
    echo_offer_list,
    echo_stats,
    echo_stats_csv,
    format_bool,
    ignore_warnings_option,
    link,
    load,
    make_table,
    me,
    page_options,
    page_params,
    request,
    terminate,
    text_or_stdin,
)
from wb.invoices import projected_invoices


@cli.group(invoke_without_command=True)
@click.pass_context
def projects(ctx):
    """Find, create, change and delete projects

    Without a command, lists your open projects."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search, owned_by=me()["short_name"])


@projects.command()
@click.argument("query", nargs=-1)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--include-closed", is_flag=True, help="Also closed projects.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search(query, customer, owned_by, include_closed, limit, offset, as_csv, as_json):
    """Search projects, open projects by default"""
    params = {"q": " ".join(query), "include_closed": format_bool(include_closed)}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    data = request("GET", "projects/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Code", "Title", "Customer", "Owned by", "Closed on")
    for project in data["items"]:
        table.add_row(
            link(project["id"], project["url"]),
            link(project["code"], project["url"]),
            project["title"],
            link(project["customer"]["name"], project["customer"]["url"]),
            project["owned_by"],
            project["closed_on"] or "",
        )
    console.print(table)
    echo_more(data, offset, "projects")


@projects.command("show")
@click.argument("project_id")
@click.option("--json", "as_json", is_flag=True)
def show_project(project_id, as_json):
    """Show a project and its offers, by ID or code (2026-0042)"""
    project = request("GET", f"projects/{project_id}/")
    # Offers require the controlling feature
    offers = request(
        "GET",
        "offers/",
        params={"project": project["id"], "limit": 1000},
        optional=True,
    )
    offers = offers["items"] if offers else None
    if as_json:
        echo_json(project | {"offers": offers})
        return
    echo_fields(
        f"{project['code']} {project['title']}",
        [
            ("ID", project["id"]),
            (
                "Customer",
                link(project["customer"]["name"], project["customer"]["url"]),
            ),
            (
                "Contact",
                link(project["contact"]["full_name"], project["contact"]["url"])
                if project["contact"]
                else None,
            ),
            ("Owned by", project["owned_by"]),
            ("Type", project["type_label"]),
            ("Internal type", project["internal_type"]),
            (
                "Campaign",
                f"{project['campaign']['code']} {project['campaign']['title']}"
                if project.get("campaign")
                else None,
            ),
            ("Cost center", project.get("cost_center")),
            ("Flat rate", project.get("flat_rate")),
            ("Budget alert at", project.get("budget_alert_at")),
            (
                "Planning mails",
                "suppressed" if project.get("suppress_planning_update_mails") else None,
            ),
            ("Closed on", project["closed_on"]),
            ("Deals", deal_links(project.get("deals"))),
            ("URL", project["url"]),
        ],
        url=project["url"],
    )
    if project["description"]:
        console.print()
        console.print(project["description"])
    if offers is not None:
        console.print()
        echo_offer_list(offers)


@projects.command()
@click.argument("project_ids", nargs=-1, type=int)
@click.option("--open", "open_", is_flag=True, help="All open projects.")
@click.option(
    "--closed-since",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Projects closed on or after this date.",
)
@click.option("--json", "as_json", is_flag=True, help="Everything as JSON.")
@click.option(
    "--csv",
    "as_csv",
    is_flag=True,
    help="Logged hours per project, service and person as CSV.",
)
def stats(project_ids, open_, closed_since, as_json, as_csv):
    """Hours, amounts and gross margins of projects"""
    params = {"ids": project_ids, "open": format_bool(open_)}
    if closed_since:
        params["closed_since"] = closed_since.date().isoformat()
    data = request("GET", "projects/stats/", params=params)
    if as_json:
        echo_json(data)
    elif as_csv:
        echo_stats_csv(data)
    else:
        echo_stats(data)


@projects.command("internal-types")
@click.option("--json", "as_json", is_flag=True)
def list_internal_types(as_json):
    """List the internal types of internal projects"""
    data = request("GET", "projects/internal-types/", params={"limit": 1000})
    if as_json:
        echo_json(data["items"])
        return
    table = make_table("ID>", "Name", "Description", "Percentage>", "Outreach")
    for row in data["items"]:
        table.add_row(
            str(row["id"]),
            row["name"],
            row["description"],
            f"{row['percentage']}%",
            "yes" if row["is_outreach"] else "",
        )
    console.print(table)


@projects.command("create")
@click.option("--title", required=True)
@click.option(
    "--customer", type=int, help="Organization ID, defaults to the contact's."
)
@click.option("--contact", type=int, help="Person ID.")
@click.option(
    "--type",
    "type_",
    type=click.Choice(["order", "maintenance", "internal"]),
    default="order",
    show_default=True,
)
@click.option(
    "--internal-type",
    help="Name or ID of the internal type, for internal projects (see `wb"
    " projects internal-types`).",
    shell_complete=complete_internal_types,
)
@click.option(
    "--owned-by",
    help="Short name, defaults to you.",
    shell_complete=complete_short_names,
)
@click.option("--description", default="")
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_project(
    title,
    customer,
    contact,
    type_,
    internal_type,
    owned_by,
    description,
    ignore_warnings,
    dry_run,
    as_json,
):
    """Create a project

    Find the customer and the contact with `wb contacts search`."""
    data = request(
        "POST",
        "projects/",
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
        json={
            "title": title,
            "description": description,
            "customer": customer,
            "contact": contact,
            "type": type_,
            "internal_type": internal_type,
            "owned_by": owned_by,
        },
    )
    _echo_saved_project(data, dry_run=dry_run, as_json=as_json)


def _echo_saved_project(data, *, dry_run, as_json):
    if as_json:
        echo_json(data)
        return
    echo_fields(
        f"{data['code']} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", link(data["customer"]["name"], data["customer"]["url"])),
            ("Owned by", data["owned_by"]),
            ("Type", data["type_label"]),
            ("Internal type", data.get("internal_type")),
            (
                "Campaign",
                f"{data['campaign']['code']} {data['campaign']['title']}"
                if data.get("campaign")
                else None,
            ),
            ("Cost center", data.get("cost_center")),
            ("Flat rate", data.get("flat_rate")),
            ("Budget alert at", data.get("budget_alert_at")),
            (
                "Planning mails",
                "suppressed" if data.get("suppress_planning_update_mails") else None,
            ),
            ("Closed on", data["closed_on"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@projects.command("update")
@click.argument("project_id", type=int)
@click.option("--title")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--contact", type=int, help="Person ID.")
@click.option(
    "--type", "type_", type=click.Choice(["order", "maintenance", "internal"])
)
@click.option(
    "--internal-type",
    help="Name or ID of the internal type (see `wb projects internal-types`),"
    " projects which aren't internal lose it.",
    shell_complete=complete_internal_types,
)
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--no-contact", is_flag=True, help="Remove the contact.")
@click.option("--campaign", type=int, help="Campaign ID (see `wb campaigns`).")
@click.option("--no-campaign", is_flag=True, help="Remove the campaign.")
@click.option("--cost-center", help="Title or ID of the cost center.")
@click.option("--no-cost-center", is_flag=True, help="Remove the cost center.")
@click.option(
    "--flat-rate",
    type=float,
    help="Hourly rate of all services, overwrites the rates of the services"
    " which haven't been invoiced.",
)
@click.option("--no-flat-rate", is_flag=True, help="Remove the flat rate.")
@click.option(
    "--budget-alert-at",
    type=float,
    help="Send a mail when the logged cost reaches this amount.",
)
@click.option("--no-budget-alert", is_flag=True, help="Remove the budget alert.")
@click.option(
    "--suppress-planning-update-mails/--send-planning-update-mails",
    default=None,
    help="Planning update mails of this project for everyone.",
)
@click.option("--close", is_flag=True, help="Close the project today.")
@click.option(
    "--closed-on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Close the project on this date.",
)
@click.option("--reopen", is_flag=True, help="Open a closed project again.")
@click.option(
    "--delete-planned-work/--keep-planned-work",
    default=None,
    help="Required when closing a project whose offers in preparation (which"
    " are discarded) have planned work.",
)
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_project(
    project_id,
    title,
    description,
    customer,
    contact,
    type_,
    internal_type,
    owned_by,
    no_contact,
    campaign,
    no_campaign,
    cost_center,
    no_cost_center,
    flat_rate,
    no_flat_rate,
    budget_alert_at,
    no_budget_alert,
    suppress_planning_update_mails,
    close,
    closed_on,
    reopen,
    delete_planned_work,
    ignore_warnings,
    dry_run,
    as_json,
):
    """Change, close or reopen a project, only the given fields

    Closing a project discards its offers in preparation. Fields of features
    you don't have (campaigns, cost centers, flat rates) can't be changed."""
    if sum(map(bool, [close, closed_on, reopen])) > 1:
        terminate("Use only one of --close, --closed-on and --reopen.")
    for option, value, empty_option, empty in [
        ("--contact", contact, "--no-contact", no_contact),
        ("--campaign", campaign, "--no-campaign", no_campaign),
        ("--cost-center", cost_center, "--no-cost-center", no_cost_center),
        ("--flat-rate", flat_rate, "--no-flat-rate", no_flat_rate),
        ("--budget-alert-at", budget_alert_at, "--no-budget-alert", no_budget_alert),
    ]:
        if value is not None and empty:
            terminate(f"Use either {option} or {empty_option}.")
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", text_or_stdin(description)),
            ("customer", customer),
            ("contact", contact),
            ("type", type_),
            ("internal_type", internal_type),
            ("owned_by", owned_by),
            ("campaign", campaign),
            ("cost_center", cost_center),
            ("flat_rate", flat_rate),
            ("budget_alert_at", budget_alert_at),
            ("suppress_planning_update_mails", suppress_planning_update_mails),
        ]
        if value is not None
    }
    for key, empty in [
        ("contact", no_contact),
        ("campaign", no_campaign),
        ("cost_center", no_cost_center),
        ("flat_rate", no_flat_rate),
        ("budget_alert_at", no_budget_alert),
    ]:
        if empty:
            data[key] = None
    if close:
        data["closed_on"] = dt.date.today().isoformat()
    elif closed_on:
        data["closed_on"] = closed_on.date().isoformat()
    elif reopen:
        data["closed_on"] = None
    if delete_planned_work is not None:
        data["delete_planned_work"] = delete_planned_work
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"projects/{project_id}/",
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
        json=data,
    )
    _echo_saved_project(data, dry_run=dry_run, as_json=as_json)


@projects.command("delete")
@click.argument("project_id")
@change_options(warnings=False)
def delete_project(project_id, dry_run, as_json):
    """Delete a project, by ID or code, e.g. one created by mistake

    Refused if offers, invoices or logged hours or costs depend on it (close
    it instead). Its services, planned work and projected invoices are
    deleted too."""
    data = request("DELETE", f"projects/{project_id}/", params=change_params(dry_run))
    echo_deleted(
        data,
        lambda data: _echo_saved_project(data, dry_run=False, as_json=False),
        what=data["code"],
        dry_run=dry_run,
        as_json=as_json,
    )


def _projected_invoice(value):
    """DATE=AMOUNT[:DESCRIPTION]"""
    day, sep, rest = value.partition("=")
    amount, _sep, description = rest.partition(":")
    try:
        dt.date.fromisoformat(day.strip())
        amount = float(amount)
    except ValueError:
        sep = ""
    if not sep:
        raise click.BadParameter(
            f"expected DATE=AMOUNT[:DESCRIPTION], e.g. 2027-01-31=5000:Phase 1,"
            f" not {value!r}."
        )
    return {
        "invoiced_on": day.strip(),
        "gross_margin": amount,
        "description": description.strip(),
    }


# The command group is in wb.invoices with the search
@projected_invoices.command("set")
@click.argument("project_id")
@click.option(
    "--invoice",
    "invoices",
    multiple=True,
    metavar="DATE=AMOUNT[:DESCRIPTION]",
    help="A projected invoice (gross margin), may be repeated.",
)
@click.option(
    "--file",
    type=click.File("r"),
    help="YAML or JSON file with a list of invoiced_on, gross_margin and"
    " description (optional).",
)
@click.option("--clear", is_flag=True, help="Delete all projected invoices.")
@change_options(warnings=False)
def set_projected_invoices(project_id, invoices, file, clear, dry_run, as_json):
    """Replace the projected invoices of a project (by ID or code)

    Like the form in the web interface: the ones not given are deleted,
    existing ones with the same date are changed. Dates must be after the
    freeze date, closed projects get no new ones."""
    items = [_projected_invoice(value) for value in invoices]
    if file:
        loaded = load(file)
        if isinstance(loaded, dict):
            loaded = loaded.get("projected_invoices")
        if not isinstance(loaded, list):
            terminate("Expected a list of projected invoices in the file.")
        items.extend(loaded)
    if bool(items) == clear:
        terminate("Pass --invoice or --file, or --clear to delete all of them.")
    data = request(
        "PUT",
        f"projects/{project_id}/projected-invoices/",
        params=change_params(dry_run),
        json={"projected_invoices": items},
    )
    if as_json:
        echo_json(data)
        return
    console.print(
        f"{data['project']['code']} {data['project']['title']}: projected gross"
        f" margin {data['total']}"
    )
    table = make_table("ID>", "Invoiced on", "Gross margin>", "Description")
    for row in data["projected_invoices"]:
        table.add_row(
            str(row["id"] or ""),
            row["invoiced_on"],
            row["gross_margin"],
            row["description"],
        )
    console.print(table)
    if dry_run:
        console.print("Dry run, nothing has been saved.")
