"""Absences"""

import datetime as dt

import click

from wb.core import (
    _bool,
    _complete_short_names,
    _echo_csv,
    _echo_fields,
    _echo_json,
    _echo_more,
    _link,
    _page_options,
    _page_params,
    _period_options,
    _period_params,
    _request,
    _table,
    cli,
    console,
)


@cli.group()
def absences():
    """Look at absences"""


@absences.command("search")
@click.option("--user", help="Short name.", shell_complete=_complete_short_names)
@click.option(
    "--reason",
    type=click.Choice([
        "vacation",
        "sickness",
        "paid",
        "school",
        "other",
        "correction",
    ]),
)
@_period_options("absences overlapping it, current and upcoming ones by default")
@_page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_absences(user, reason, period, since, until, limit, offset, as_csv, as_json):
    """Search absences, current and upcoming ones by default"""
    params = _period_params(period, since, until) or {
        "since": dt.date.today().isoformat()
    }
    if user:
        params["user"] = user
    if reason:
        params["reason"] = reason
    data = _request("GET", "absences/", params=params | _page_params(limit, offset))
    if as_csv:
        _echo_csv(data["items"])
        _echo_more(data, offset)
        return
    if as_json:
        _echo_json(data)
        return
    table = _table("User", "Starts on", "Ends on", "Days>", "Reason", "Description")
    for absence in data["items"]:
        table.add_row(
            _link(absence["user"], absence["url"]),
            absence["starts_on"],
            absence["ends_on"] or "",
            absence["days"],
            absence["reason"],
            absence["description"],
        )
    console.print(table)
    _echo_more(data, offset, "absences")


@absences.command("create")
@click.option("--starts-on", type=click.DateTime(formats=["%Y-%m-%d"]), required=True)
@click.option(
    "--ends-on",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="In the same year, leave out for a single day.",
)
@click.option("--days", type=float, required=True, help="Working days, e.g. 0.5.")
@click.option(
    "--reason",
    type=click.Choice([
        "vacation",
        "sickness",
        "paid",
        "school",
        "other",
        "correction",
    ]),
    required=True,
)
@click.option("--description", required=True)
@click.option(
    "--user", help="Short name, defaults to you.", shell_complete=_complete_short_names
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_absence(
    starts_on, ends_on, days, reason, description, user, dry_run, as_json
):
    """Create an absence like in Workbench, e.g. your vacation"""
    data = _request(
        "POST",
        "absences/",
        params={"dry_run": _bool(dry_run)},
        json={
            "user": user,
            "starts_on": starts_on.date().isoformat(),
            "ends_on": ends_on.date().isoformat() if ends_on else None,
            "days": days,
            "reason": reason,
            "description": description,
        },
    )
    if as_json:
        _echo_json(data)
        return
    _echo_fields(
        f"{data['user']}: {data['reason']}",
        [
            ("ID", data["id"]),
            ("Starts on", data["starts_on"]),
            ("Ends on", data["ends_on"]),
            ("Days", data["days"]),
            ("Description", data["description"]),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if dry_run:
        console.print("Dry run, nothing has been saved.")
