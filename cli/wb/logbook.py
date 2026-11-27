"""Logged hours and costs"""

import click

from wb.core import (
    change_options,
    change_params,
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_json,
    echo_more,
    format_bool,
    ignore_warnings_option,
    link,
    make_table,
    me,
    page_options,
    page_params,
    period_options,
    period_params,
    request,
    terminate,
    text_or_stdin,
)


def _echo_entry(data, amount, *, dry_run, as_json, prefix):
    if as_json:
        echo_json(data)
        return
    if dry_run:
        prefix = "Dry run, nothing changed: " + prefix
    console.print(
        f"{prefix}{link(data['id'] or '(new)', data['url'])} {data['rendered_on']}"
        f" {data['rendered_by']} {amount}"
        f" | {link(data['project']['code'], data['project']['url'])}"
        f" {data['service']} ({data['service_id']}) | {data['description']}"
    )


def _echo_hours(data, **kwargs):
    amount = f"{data['hours']}h"
    if data["hours_for_invoicing"] is not None:
        amount += f" → {data['hours_for_invoicing']}h"
    _echo_entry(data, amount, **kwargs)


def _echo_cost(data, **kwargs):
    amount = data["cost"]
    if data["third_party_costs"] is not None:
        amount += f" (third party {data['third_party_costs']})"
    if data["are_expenses"]:
        amount += " (expenses)"
    _echo_entry(data, amount, **kwargs)


def _values(**values):
    """The given values, descriptions given as ``-`` are read from stdin"""
    data = {key: value for key, value in values.items() if value is not None}
    if "description" in data:
        data["description"] = text_or_stdin(data["description"])
    return data


def _clear(data, field, flag):
    if flag and data.get(field) is not None:
        option = field.replace("_", "-")
        terminate(f"--clear-{option} and --{option} contradict each other.")
    if flag:
        data[field] = None


_rendered_on_option = click.option(
    "--rendered-on",
    type=click.DateTime(["%Y-%m-%d"]),
    help="Date the work was done (YYYY-MM-DD), defaults to today.",
)
_rendered_by_option = click.option(
    "--rendered-by",
    help="Short name, defaults to you. Hours of others are reported to"
    " personnel administration.",
    shell_complete=complete_short_names,
)


def _date(value):
    return value.date().isoformat() if value else None


@cli.group(invoke_without_command=True)
@click.pass_context
def hours(ctx):
    """Look at, log, change, move and delete hours

    Without a command, lists your hours of this week."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_hours, rendered_by=me()["short_name"], period="this-week")


@hours.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.", shell_complete=complete_short_names)
@click.option(
    "--hours-for-invoicing", is_flag=True, help="Only entries with hours for invoicing."
)
@click.option(
    "--invoiced/--not-invoiced",
    default=None,
    help="Only entries which are (not) on an invoice.",
)
@period_options("filters the date the work was done")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_hours(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    hours_for_invoicing,
    invoiced,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search logged hours, newest first

    Hours for invoicing (what the work is worth if that is more than the time
    spent) are shown after an arrow."""
    params = {
        "q": " ".join(query),
        "hours_for_invoicing": format_bool(hours_for_invoicing),
    }
    if invoiced is not None:
        params["invoiced"] = format_bool(invoiced)
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    params |= period_params(period, since, until)
    data = request("GET", "logbook/hours/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
        "ID>",
        "Rendered on",
        "By",
        "Project",
        "Service",
        "Hours>",
        "Description",
        show_footer=True,
    )
    for row in data["items"]:
        table.add_row(
            link(row["id"], row["url"]),
            row["rendered_on"],
            row["rendered_by"],
            link(row["project"]["code"], row["project"]["url"]),
            f"{row['service']} ({row['service_id']})",
            row["hours"]
            if row["hours_for_invoicing"] is None
            else f"{row['hours']} → {row['hours_for_invoicing']}",
            row["description"],
        )
    table.columns[1].footer = "Total"
    table.columns[5].footer = data["total_hours"]
    console.print(table)
    echo_more(data, offset, "entries", note="The total includes all of them.")


@hours.command("create")
@click.argument("service_id", type=int)
@click.argument("hours", type=float)
@click.argument("description")
@_rendered_on_option
@_rendered_by_option
@click.option(
    "--hours-for-invoicing",
    type=float,
    help="Value and invoice the work with these hours, e.g. if it's worth more"
    " than the time spent.",
)
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_hours(
    service_id,
    hours,
    description,
    rendered_on,
    rendered_by,
    hours_for_invoicing,
    ignore_warnings,
    dry_run,
    as_json,
):
    """Log hours on a service (`wb services search` finds its ID)

    Checked like in the web interface: warnings (e.g. a duplicate, a missing
    break) stop with their code, `--ignore-warning CODE` accepts them after
    you've checked. A DESCRIPTION of `-` is read from stdin."""
    data = request(
        "POST",
        "logbook/hours/",
        params=change_params(dry_run, ignore_warnings),
        json=_values(
            service=service_id,
            hours=hours,
            description=description,
            rendered_on=_date(rendered_on),
            rendered_by=rendered_by,
            hours_for_invoicing=hours_for_invoicing,
        ),
    )
    _echo_hours(data, dry_run=dry_run, as_json=as_json, prefix="Logged ")


@hours.command("update")
@click.argument("hours_id", type=int)
@click.option(
    "--service",
    type=int,
    help="Another service; one of another open project moves the entry there.",
)
@click.option("--hours", type=float)
@click.option("--description", help="`-` reads it from stdin.")
@_rendered_on_option
@_rendered_by_option
@click.option("--hours-for-invoicing", type=float)
@click.option(
    "--clear-hours-for-invoicing",
    is_flag=True,
    help="Value and invoice the work with the hours again.",
)
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_hours(
    hours_id,
    service,
    hours,
    description,
    rendered_on,
    rendered_by,
    hours_for_invoicing,
    clear_hours_for_invoicing,
    ignore_warnings,
    dry_run,
    as_json,
):
    """Change logged hours, only the given fields

    Like in the web interface, hours of past weeks keep their date, person
    and hours, invoiced hours only allow changing the description. A
    `--service` of another open project moves the hours there, not when
    they have been invoiced or their project has been closed."""
    data = _values(
        service=service,
        hours=hours,
        description=description,
        rendered_on=_date(rendered_on),
        rendered_by=rendered_by,
        hours_for_invoicing=hours_for_invoicing,
    )
    _clear(data, "hours_for_invoicing", clear_hours_for_invoicing)
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"logbook/hours/{hours_id}/",
        params=change_params(dry_run, ignore_warnings),
        json=data,
    )
    _echo_hours(data, dry_run=dry_run, as_json=as_json, prefix="Changed ")


@hours.command("delete")
@click.argument("hours_id", type=int)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def delete_hours(hours_id, dry_run, as_json):
    """Delete logged hours

    Like in the web interface, not when they have been invoiced or are from
    past weeks."""
    data = request(
        "DELETE", f"logbook/hours/{hours_id}/", params=change_params(dry_run)
    )
    _echo_hours(data, dry_run=dry_run, as_json=as_json, prefix="Deleted ")


def _move_command(group, kind, echo):
    """``wb hours|costs move``: entries of a project to another service of
    the same project at once"""

    @group.command(
        "move",
        help=f"""Move {kind} of a project to another service of the project

    All or none, like the logbook batch update of the web interface: not
    for invoiced entries or closed projects. `wb {kind} update ID --service`
    moves single entries to other projects.""",
    )
    @click.option("--project", type=int, required=True, help="Project ID.")
    @click.option(
        "--entry",
        "entries",
        type=int,
        multiple=True,
        required=True,
        help=f"ID of {kind} which haven't been invoiced (repeatable).",
    )
    @click.option(
        "--service",
        type=int,
        required=True,
        help="ID of another service of the same project.",
    )
    @change_options()
    def move(project, entries, service, ignore_warnings, dry_run, as_json):
        data = request(
            "POST",
            f"projects/{project}/logbook/move/",
            params=change_params(dry_run, ignore_warnings),
            json={"kind": kind, "entries": list(entries), "service": service},
        )
        if as_json:
            echo_json(data)
            return
        for row in data:
            echo(row, dry_run=dry_run, as_json=False, prefix="Moved ")

    return move


move_hours = _move_command(hours, "hours", _echo_hours)


@cli.group()
def costs():
    """Look at, log, change, move and delete costs"""


@costs.command("search")
@click.argument("query", nargs=-1)
@click.option("--project", type=int, help="Project ID.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--offer", type=int, help="Offer ID.")
@click.option("--service", type=int, help="Service ID.")
@click.option("--rendered-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--expenses", is_flag=True, help="Paid from someone's own pocket.")
@period_options("filters the date the work was done")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_costs(
    query,
    project,
    customer,
    offer,
    service,
    rendered_by,
    expenses,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search logged costs, newest first"""
    params = {"q": " ".join(query), "expenses": format_bool(expenses)}
    for key, value in [
        ("project", project),
        ("customer", customer),
        ("offer", offer),
        ("service", service),
        ("rendered_by", rendered_by),
    ]:
        if value:
            params[key] = value
    params |= period_params(period, since, until)
    data = request("GET", "logbook/costs/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
        "ID>",
        "Rendered on",
        "By",
        "Project",
        "Service",
        "Cost>",
        "Third party>",
        "Description",
        show_footer=True,
    )
    for row in data["items"]:
        table.add_row(
            link(row["id"], row["url"]),
            row["rendered_on"],
            row["rendered_by"],
            link(row["project"]["code"], row["project"]["url"]),
            f"{row['service']} ({row['service_id']})",
            row["cost"],
            row["third_party_costs"] or "",
            row["description"] + (" (expenses)" if row["are_expenses"] else ""),
        )
    table.columns[1].footer = "Total"
    table.columns[5].footer = data["total_cost"]
    table.columns[6].footer = data["total_third_party_costs"]
    console.print(table)
    echo_more(data, offset, "entries", note="The totals include all of them.")


_cost_options = [
    click.option(
        "--third-party-costs",
        type=float,
        help="Total incl. tax for third parties contained in the cost.",
    ),
    click.option(
        "--expense-currency",
        help="Currency of expenses paid in a foreign currency, with --expense-cost.",
    ),
    click.option(
        "--expense-cost", type=float, help="Expenses in the foreign currency."
    ),
    _rendered_on_option,
    _rendered_by_option,
]


def _with_cost_options(fn):
    for option in reversed(_cost_options):
        fn = option(fn)
    return fn


@costs.command("create")
@click.argument("service_id", type=int)
@click.argument("cost", type=float)
@click.argument("description")
@_with_cost_options
@click.option(
    "--expenses",
    is_flag=True,
    help="Paid from your own pocket, needs --third-party-costs.",
)
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_cost(
    service_id, cost, description, expenses, ignore_warnings, dry_run, as_json, **values
):
    """Log costs (excl. tax) on a service (`wb services search` finds its ID)

    Checked like in the web interface: warnings stop with their code,
    `--ignore-warning CODE` accepts them after you've checked. A DESCRIPTION
    of `-` is read from stdin."""
    values["rendered_on"] = _date(values["rendered_on"])
    data = request(
        "POST",
        "logbook/costs/",
        params=change_params(dry_run, ignore_warnings),
        json=_values(
            service=service_id,
            cost=cost,
            description=description,
            are_expenses=expenses or None,
            **values,
        ),
    )
    _echo_cost(data, dry_run=dry_run, as_json=as_json, prefix="Logged ")


@costs.command("update")
@click.argument("cost_id", type=int)
@click.option(
    "--service",
    type=int,
    help="Another service; one of another open project moves the entry there.",
)
@click.option("--cost", type=float, help="Excl. tax.")
@click.option("--description", help="`-` reads it from stdin.")
@_with_cost_options
@click.option(
    "--clear-third-party-costs", is_flag=True, help="Remove the third party costs."
)
@click.option(
    "--expenses/--no-expenses", default=None, help="Paid from your own pocket?"
)
@ignore_warnings_option
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_cost(
    cost_id,
    clear_third_party_costs,
    expenses,
    ignore_warnings,
    dry_run,
    as_json,
    **values,
):
    """Change logged costs, only the given fields

    Like in the web interface, invoiced costs keep their service, date,
    person and amounts, costs of expense reports their date, person and
    expenses. A `--service` of another open project moves the costs there,
    not when they have been invoiced or their project has been closed."""
    values["rendered_on"] = _date(values["rendered_on"])
    data = _values(**values, are_expenses=expenses)
    _clear(data, "third_party_costs", clear_third_party_costs)
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"logbook/costs/{cost_id}/",
        params=change_params(dry_run, ignore_warnings),
        json=data,
    )
    _echo_cost(data, dry_run=dry_run, as_json=as_json, prefix="Changed ")


@costs.command("delete")
@click.argument("cost_id", type=int)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def delete_cost(cost_id, dry_run, as_json):
    """Delete logged costs

    Like in the web interface, not when they have been invoiced or are part
    of an expense report."""
    data = request("DELETE", f"logbook/costs/{cost_id}/", params=change_params(dry_run))
    _echo_cost(data, dry_run=dry_run, as_json=as_json, prefix="Deleted ")


move_costs = _move_command(costs, "costs", _echo_cost)
