"""Deals"""

import click

from wb.core import (
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_fields,
    echo_json,
    echo_more,
    echo_period,
    format_amount,
    format_bool,
    link,
    make_table,
    page_options,
    page_params,
    period_options,
    period_params,
    request,
    terminate,
    text_or_stdin,
    users_options,
)


@cli.group()
def deals():
    """Look at and add to the sales pipeline"""


@deals.command("search")
@click.argument("query", nargs=-1)
@click.option(
    "--status", type=click.Choice(["open", "accepted", "declined"]), default="open"
)
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@period_options("filters the decision date (closed or expected)")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_deals(
    query,
    status,
    customer,
    owned_by,
    period,
    since,
    until,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search deals, open deals by default"""
    params = {"q": " ".join(query), "status": status}
    if customer:
        params["customer"] = customer
    if owned_by:
        params["owned_by"] = owned_by
    params |= period_params(period, since, until)
    data = request("GET", "deals/", params=params | page_params(limit, offset))
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
        "Probability",
        "Decision expected on",
        "Value>",
    )
    for deal in data["items"]:
        table.add_row(
            link(deal["id"], deal["url"]),
            deal["title"],
            link(deal["customer"]["name"], deal["customer"]["url"]),
            deal["owned_by"],
            deal["probability"],
            deal["decision_expected_on"] or "",
            deal["value"],
        )
    console.print(table)
    echo_more(data, offset, "deals")


@deals.command("show")
@click.argument("deal_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_deal(deal_id, as_json):
    """Show a deal"""
    data = request("GET", f"deals/{deal_id}/")
    echo_json(data) if as_json else _echo_deal(data)


def _key_values(values, option):
    """Parse ``KEY=VALUE`` options into a dict"""
    result = {}
    for pair in values:
        key, sep, value = pair.partition("=")
        if not sep:
            terminate(f"{option} expects KEY=VALUE, got {pair!r}.")
        result[key.strip()] = value.strip()
    return result


def _echo_saved_deal(data, *, dry_run, as_json):
    if as_json:
        echo_json(data)
        return
    _echo_deal(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@deals.command("update")
@click.argument("deal_id", type=int)
@click.option("--title")
@click.option("--description", help="The text, or - to read it from stdin.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option("--contact", type=int, help="Person ID.")
@click.option("--probability", type=click.Choice(["low", "normal", "high"]))
@click.option(
    "--decision-expected-on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Required for a high probability.",
)
@click.option(
    "--value",
    "values",
    multiple=True,
    help="TYPE=AMOUNT, e.g. Design=5000; TYPE= removes the value.",
)
@click.option("--attribute", "attributes", multiple=True, help="GROUP=ATTRIBUTE.")
@click.option("--owned-by", help="Short name.", shell_complete=complete_short_names)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_deal(
    deal_id,
    title,
    description,
    customer,
    contact,
    probability,
    decision_expected_on,
    values,
    attributes,
    owned_by,
    dry_run,
    as_json,
):
    """Change a deal, only the given fields

    Close or reopen deals with `wb deals close` and `wb deals reopen`."""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("description", text_or_stdin(description)),
            ("customer", customer),
            ("contact", contact),
            ("probability", probability),
            ("owned_by", owned_by),
        ]
        if value is not None
    }
    if decision_expected_on:
        data["decision_expected_on"] = decision_expected_on.date().isoformat()
    if values:
        data["values"] = {
            key: value or None for key, value in _key_values(values, "--value").items()
        }
    if attributes:
        data["attributes"] = _key_values(attributes, "--attribute")
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"deals/{deal_id}/",
        params={"dry_run": format_bool(dry_run)},
        json=data,
    )
    _echo_saved_deal(data, dry_run=dry_run, as_json=as_json)


@deals.command("close")
@click.argument("deal_id", type=int)
@click.argument("status", type=click.Choice(["accepted", "declined"]))
@click.option(
    "--closing-type",
    required=True,
    help="Award of contract or reason for losing, unknown ones are rejected"
    " with a list of the choices.",
)
@click.option("--notice", default="", help="The text, or - to read it from stdin.")
@click.option(
    "--closed-on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Defaults to today.",
)
@click.option(
    "--offer",
    "offers",
    type=int,
    multiple=True,
    help="Related offer to accept or decline too, can be repeated. Defaults to"
    " those which haven't been accepted yet.",
)
@click.option("--keep-offers", is_flag=True, help="Leave the related offers alone.")
@click.option(
    "--delete-planned-work/--keep-planned-work",
    default=None,
    help="Required when declining offers with planned work.",
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def close_deal(
    deal_id,
    status,
    closing_type,
    notice,
    closed_on,
    offers,
    keep_offers,
    delete_planned_work,
    dry_run,
    as_json,
):
    """Accept or decline a deal and its related offers like in Workbench"""
    if offers and keep_offers:
        terminate("--offer and --keep-offers contradict each other.")
    data = {
        "status": status,
        "closing_type": closing_type,
        "closing_notice": text_or_stdin(notice),
        "delete_planned_work": delete_planned_work,
    }
    if closed_on:
        data["closed_on"] = closed_on.date().isoformat()
    if offers or keep_offers:
        data["offers"] = list(offers)
    data = request(
        "POST",
        f"deals/{deal_id}/status/",
        params={"dry_run": format_bool(dry_run)},
        json=data,
    )
    _echo_saved_deal(data, dry_run=dry_run, as_json=as_json)


@deals.command("reopen")
@click.argument("deal_id", type=int)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def reopen_deal(deal_id, dry_run, as_json):
    """Open a closed deal again"""
    data = request(
        "POST",
        f"deals/{deal_id}/status/",
        params={"dry_run": format_bool(dry_run)},
        json={"status": "open"},
    )
    _echo_saved_deal(data, dry_run=dry_run, as_json=as_json)


@deals.command("stats")
@period_options("defaults to this week")
@users_options
@click.option("--csv", "as_csv", is_flag=True, help="The rows of the main table.")
@click.option("--json", "as_json", is_flag=True)
def deal_stats(period, since, until, users, team, as_csv, as_json):
    """Deals accepted and declined in a period

    Users filter the deals' owners; accepted deals are split between users
    by their contributions."""
    data = request(
        "GET",
        "deals/stats/",
        params=period_params(period, since, until, users=users, team=team),
    )
    if as_csv:
        echo_csv(
            [deal | {"status": "accepted"} for deal in data["accepted"]["deals"]]
            + [deal | {"status": "declined"} for deal in data["declined"]["deals"]]
        )
        return
    if as_json:
        echo_json(data)
        return
    echo_period(data)
    accepted = data["accepted"]
    console.print(
        f"Accepted: {accepted['count']} deals, {format_amount(accepted['sum'])}"
        + (
            f" (target {format_amount(accepted['target'])})"
            if float(accepted["target"])
            else ""
        )
    )
    if accepted["deals"]:
        table = make_table("Value type", "Accepted>", "Target>", "Median age>")
        for row in accepted["by_value_type"]:
            table.add_row(
                row["type"],
                format_amount(row["sum"]),
                format_amount(row["target"]),
                f"{row['median_age_days']} days"
                if row["median_age_days"] is not None
                else "",
            )
        console.print(table)
        table = make_table("User", "Deals>", "Accepted>")
        for row in accepted["by_user"]:
            table.add_row(row["user"], str(row["count"]), format_amount(row["sum"]))
        console.print(table)
        table = make_table(
            "Code",
            "Title",
            "Customer",
            "Owner",
            "Closed on",
            "Value>",
            title="Accepted",
        )
        for deal in accepted["deals"]:
            table.add_row(
                link(deal["code"], deal["url"]),
                deal["title"],
                link(deal["customer"]["name"], deal["customer"]["url"]),
                deal["owned_by"],
                deal["closed_on"],
                format_amount(deal["value"]),
            )
        console.print(table)
    declined = data["declined"]
    console.print(
        f"Declined: {declined['count']} deals, {format_amount(declined['sum'])}"
    )
    if declined["deals"]:
        table = make_table(
            "Code", "Title", "Customer", "Closing type", "Value>", title="Declined"
        )
        for deal in declined["deals"]:
            table.add_row(
                link(deal["code"], deal["url"]),
                deal["title"],
                link(deal["customer"]["name"], deal["customer"]["url"]),
                deal["closing_type"],
                format_amount(deal["value"]),
            )
        console.print(table)


@deals.command("history")
@period_options("defaults to this week")
@users_options
@click.option("--json", "as_json", is_flag=True)
def deal_history(period, since, until, users, team, as_json):
    """Changes of deals in a period, users filter who made them"""
    data = request(
        "GET",
        "deals/history/",
        params=period_params(period, since, until, users=users, team=team),
    )
    if as_json:
        echo_json(data)
        return
    echo_period(data)
    for change in data["changes"]:
        deal = change["deal"]
        console.print(
            link(f"{deal['code']} {deal['title']}", deal["url"])
            if deal
            else "(deleted deal)",
            style="bold",
        )
        console.print(
            f"{change['created_at'][:16].replace('T', ' ')}, {change['user']}",
            style="dim",
        )
        for text in change["changes"]:
            console.print(f"  {text}")


@deals.command("create")
@click.option("--title", required=True)
@click.option(
    "--customer", type=int, help="Organization ID, defaults to the contact's."
)
@click.option("--contact", type=int, help="Person ID.")
@click.option(
    "--probability", type=click.Choice(["low", "normal", "high"]), required=True
)
@click.option(
    "--decision-expected-on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Required for a high probability.",
)
@click.option("--value", "values", multiple=True, help="TYPE=AMOUNT, e.g. Design=5000.")
@click.option("--attribute", "attributes", multiple=True, help="GROUP=ATTRIBUTE.")
@click.option(
    "--owned-by",
    help="Short name, defaults to you.",
    shell_complete=complete_short_names,
)
@click.option("--description", default="")
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_deal(
    title,
    customer,
    contact,
    probability,
    decision_expected_on,
    values,
    attributes,
    owned_by,
    description,
    dry_run,
    as_json,
):
    """Create a deal, you are its main driving force

    Find the customer and the contact with `wb contacts search`. Unknown
    value types and attributes are rejected with a list of the choices."""
    data = request(
        "POST",
        "deals/",
        params={"dry_run": format_bool(dry_run)},
        json={
            "title": title,
            "description": description,
            "customer": customer,
            "contact": contact,
            "owned_by": owned_by,
            "probability": probability,
            "decision_expected_on": decision_expected_on.date().isoformat()
            if decision_expected_on
            else None,
            "values": _key_values(values, "--value"),
            "attributes": _key_values(attributes, "--attribute"),
        },
    )
    _echo_saved_deal(data, dry_run=dry_run, as_json=as_json)


def _echo_deal(data):
    echo_fields(
        f"{data['code'] or '(new deal)'} {data['title']}",
        [
            ("ID", data["id"]),
            ("Customer", link(data["customer"]["name"], data["customer"]["url"])),
            ("Owned by", data["owned_by"]),
            ("Contributors", ", ".join(data["contributors"])),
            ("Status", data["status"]),
            ("Probability", data["probability"]),
            ("Decision expected on", data["decision_expected_on"]),
            ("Closed on", data["closed_on"]),
            ("Closing type", data["closing_type"]),
            ("Related offers", ", ".join(data["related_offers"])),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    table = make_table("Value type", "Value>", show_footer=True)
    for value in data["values"]:
        table.add_row(value["type"], value["value"])
    table.columns[0].footer = "Total"
    table.columns[1].footer = data["value"]
    console.print(table)
    for text in (data["description"], data["closing_notice"]):
        if text:
            console.print(text)
