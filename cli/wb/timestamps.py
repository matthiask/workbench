"""Timestamps"""

import datetime as dt
import re
from urllib.parse import quote

import click

from wb.core import cli, console, echo_json, link, make_table, request


@cli.group()
def timestamps():
    """Start and stop tasks, log the hours in Workbench"""


def _time(value):
    """Hours and minutes of an ISO 8601 timestamp in Workbench's time zone"""
    return dt.datetime.fromisoformat(value).strftime("%H:%M") if value else "?"


def _create_timestamp(type_, args, as_json):
    """The first argument may be a time (13:30) or minutes relative to now
    (-5, +15), the others are notes"""
    data = {"type": type_}
    if args and re.fullmatch(r"[0-9]{1,2}:[0-9]{2}", args[0]):
        data["time"] = args[0]
        args = args[1:]
    elif args and re.fullmatch(r"[-+][0-9]+", args[0]):
        data["minutes"] = int(args[0])
        args = args[1:]
    data["notes"] = " ".join(args)
    timestamp = request("POST", "timestamps/", json=data)
    if as_json:
        echo_json(timestamp)
        return
    _echo_timestamp(timestamp)


def _echo_timestamp(timestamp, prefix=""):
    """The timestamp and the duration of the task it stopped"""
    text = (
        f"{prefix}{timestamp['code']}: {timestamp['type']}"
        f" at {_time(timestamp['created_at'])}"
        + (f", {timestamp['notes']}" if timestamp["notes"] else "")
    )
    if (slice := timestamp["slice"]) and slice["hours"] and slice["ends_at"]:
        text += f" ({slice['hours']}h since {_time(slice['starts_at'])})"
    console.print(text)


_TIMESTAMP_HELP = """

    \b
    wb timestamps {0}                   # Now
    wb timestamps {0} -5 Notes          # 5 minutes ago, with notes
    wb timestamps {0} 13:30             # At 13:30
    wb timestamps {0} +15               # In 15 minutes"""


@timestamps.command(
    context_settings={"ignore_unknown_options": True},
    help="Start a task" + _TIMESTAMP_HELP.format("start"),
)
@click.argument("args", nargs=-1)
@click.option("--json", "as_json", is_flag=True)
def start(args, as_json):
    _create_timestamp("start", args, as_json)


@timestamps.command(
    context_settings={"ignore_unknown_options": True},
    help="Stop a task" + _TIMESTAMP_HELP.format("stop"),
)
@click.argument("args", nargs=-1)
@click.option("--json", "as_json", is_flag=True)
def stop(args, as_json):
    _create_timestamp("stop", args, as_json)


@timestamps.command("list")
@click.option(
    "--day", type=click.DateTime(formats=["%Y-%m-%d"]), help="Defaults to today."
)
@click.option("--json", "as_json", is_flag=True)
def list_timestamps(day, as_json):
    """The day's timestamps, logged hours and breaks

    Unlogged slices link to the form for logging their hours."""
    params = {"day": day.date().isoformat()} if day else {}
    data = request("GET", "timestamps/", params=params)
    echo_json(data) if as_json else _echo_timestamps(data)


def _echo_timestamps(data):
    table = make_table(
        "Code",
        "From",
        "Until",
        "Hours>",
        "Description",
        "Project",
        "",
        title=link(f"Timestamps {data['day']}", data["url"]),
        show_footer=True,
    )
    for slice in data["slices"]:
        project = slice["project"]
        table.add_row(
            slice["timestamp_code"] or "",
            _time(slice["starts_at"]),
            _time(slice["ends_at"]),
            slice["hours"] or "",
            slice["description"] + (f" {slice['comment']}" if slice["comment"] else ""),
            link(project["code"], project["url"]) if project else "",
            link("Log hours", slice["log_hours_url"]) if slice["log_hours_url"] else "",
            style=None if slice["is_logged"] else "bold",
        )
    table.columns[2].footer = "Logged"
    table.columns[3].footer = data["logged_hours"]
    console.print(table)
    console.print(f"Logged this week: {data['weekly_hours']}h")
    if data["running_since"]:
        console.print(
            f"Running since {_time(data['running_since'])} ({data['running_hours']}h)",
            style="bold",
        )


def _echo_deleted(timestamp, as_json):
    """The deleted timestamp and the day's renumbered timestamps"""
    if as_json:
        echo_json(timestamp)
        return
    _echo_timestamp(timestamp, "Deleted ")
    day = dt.datetime.fromisoformat(timestamp["created_at"]).date().isoformat()
    _echo_timestamps(request("GET", "timestamps/", params={"day": day}))


@timestamps.command("delete")
@click.argument("timestamp")
@click.option(
    "--day",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Day of the code, defaults to today.",
)
@click.option("--json", "as_json", is_flag=True)
def delete_timestamp(timestamp, day, as_json):
    """Delete a timestamp by its code (T1, T2, ...) or its ID

    `wb timestamps list` shows the codes. Deleting a timestamp renumbers the
    following ones, the new codes are shown afterwards."""
    params = {"day": day.date().isoformat()} if day else {}
    _echo_deleted(
        request("DELETE", f"timestamps/{quote(timestamp, safe='')}/", params=params),
        as_json,
    )


@timestamps.command()
@click.option("--json", "as_json", is_flag=True)
def undo(as_json):
    """Delete the latest timestamp of today"""
    _echo_deleted(request("DELETE", "timestamps/latest/"), as_json)
