"""Planning"""

import csv
import sys

import click

from wb.core import (
    cli,
    complete_short_names,
    console,
    echo_json,
    echo_period,
    format_bool,
    format_error,
    format_hours,
    link,
    load,
    make_table,
    me,
    period_options,
    period_params,
    request,
    terminate,
    text_or_stdin,
    users_options,
)


@cli.group(invoke_without_command=True)
@click.pass_context
def planning(ctx):
    """Plan projects: milestones and planned work

    Without a command, shows your planning of the next twelve weeks."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(planning_export, users=(me()["short_name"],))


@planning.command("export")
@click.option("--project", type=int, help="Project ID.")
@click.option("--campaign", type=int, help="Campaign ID.")
@period_options(
    "defaults to the whole planning of projects and campaigns, otherwise"
    " to the next twelve weeks"
)
@users_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per work and week.")
@click.option("--json", "as_json", is_flag=True)
def planning_export(
    project, campaign, period, since, until, users, team, as_csv, as_json
):
    """Export planned work, milestones and the capacity per week

    The capacity (hours not planned yet, less absences and holidays) is shown
    when filtering by users or a team."""
    params = period_params(period, since, until, users=users, team=team)
    if project:
        params["project"] = project
    if campaign:
        params["campaign"] = campaign
    data = request("GET", "planning/export/", params=params)
    if as_json:
        echo_json(data)
    elif as_csv:
        _echo_planning_csv(data)
    else:
        _echo_planning(data)


def _echo_planning_csv(data):
    weeks = {week["week"] for week in data["weeks"]}
    writer = csv.writer(sys.stdout)
    writer.writerow([
        "week",
        "project_id",
        "project",
        "project_title",
        "offer",
        "milestone",
        "work_id",
        "title",
        "user",
        "service_type",
        "is_provisional",
        "hours",
    ])
    rows = [
        (week, work)
        for work in data["planned_work"]
        for week in work["weeks"]
        if week in weeks
    ]
    for week, work in sorted(rows, key=lambda row: (row[0], row[1]["id"])):
        project = work["project"]
        writer.writerow([
            week,
            project["id"],
            project["code"],
            project["title"],
            work["offer"]["code"] if work["offer"] else "",
            work["milestone"] or "",
            work["id"],
            work["title"],
            work["user"],
            work["service_type"] or "",
            work["is_provisional"],
            work["hours_per_week"],
        ])


def _echo_planning(data):
    if not data["since"]:
        console.print("Nothing planned yet.")
        return
    echo_period(data)
    table = make_table(
        "Project",
        "Offer",
        "Title",
        "User",
        "First week",
        "Last week",
        "Hours>",
        "Per week>",
        title="Planned work",
    )
    for work in data["planned_work"]:
        project = work["project"]
        table.add_row(
            link(project["code"], project["url"]),
            work["offer"]["code"] if work["offer"] else "",
            link(work["title"], work["url"]),
            work["user"],
            work["weeks"][0],
            work["weeks"][-1],
            format_hours(work["planned_hours"]),
            format_hours(work["hours_per_week"]),
            style="dim" if work["is_provisional"] else None,
        )
    console.print(table)
    if any(work["is_provisional"] for work in data["planned_work"]):
        console.print("Provisional work is dimmed.", style="dim")
    if data["milestones"]:
        table = make_table("Date", "Project", "Milestone", "Hours>", title="Milestones")
        for milestone in data["milestones"]:
            table.add_row(
                milestone["date"],
                link(milestone["project"]["code"], milestone["project"]["url"]),
                link(milestone["title"], milestone["url"]),
                format_hours(milestone["estimated_total_hours"]),
            )
        console.print(table)
    if data["external_work"]:
        table = make_table(
            "Project",
            "Title",
            "Provided by",
            "First week",
            "Last week",
            title="External work",
        )
        for work in data["external_work"]:
            table.add_row(
                link(work["project"]["code"], work["project"]["url"]),
                link(work["title"], work["url"]),
                work["provided_by"],
                work["weeks"][0],
                work["weeks"][-1],
            )
        console.print(table)
    capacity = data["capacity"] or []
    table = make_table(
        "Week",
        "Planned>",
        "Provisional>",
        *(f"{row['user']} free>" for row in capacity),
        title="Per week",
    )
    for week in data["weeks"]:
        table.add_row(
            week["week"],
            format_hours(week["planned"]),
            format_hours(week["provisional"]),
            *(format_hours(row["weeks"][week["week"]]) for row in capacity),
        )
    console.print(table)


@planning.command("context")
@click.argument("project_id", type=int)
def planning_context(project_id):
    """Print everything needed to plan a project and the import schema

    Feed this to an LLM together with the plan, e.g. the offer and a timeline."""
    echo_json(request("GET", f"projects/{project_id}/planning/context/"))


def _echo_planned_work(planned_work):
    table = make_table(
        "ID>",
        "Planned work",
        "User",
        "Service type",
        "Offer",
        "Weeks",
        "Hours>",
        "Provisional",
    )
    for pw in planned_work:
        weeks = pw["weeks"]
        table.add_row(
            str(pw["id"] or "(new)"),
            pw["title"],
            pw["user"],
            pw["service_type"] or "",
            pw["offer"] or "",
            f"{weeks[0]} – {weeks[-1]} ({len(weeks)})" if len(weeks) > 1 else weeks[0],
            pw["planned_hours"],
            "yes" if pw["is_provisional"] else "",
        )
    console.print(table)


def _echo_import_result(data, *, dry_run, as_json):
    if as_json:
        echo_json(data)
        return
    if data["milestones"]:
        table = make_table("Milestone", "Date", "Phase starts on", "Estimated hours>")
        for milestone in data["milestones"]:
            table.add_row(
                milestone["title"],
                milestone["date"],
                milestone["phase_starts_on"] or "",
                milestone["estimated_total_hours"],
            )
        console.print(table)
    if data["planned_work"]:
        _echo_planned_work(data["planned_work"])
    for key, what in [
        ("deleted_milestones", "milestones"),
        ("deleted_planned_work", "planned work"),
    ]:
        if ids := data.get(key):
            console.print(f"Deleted {what}: {', '.join(map(str, ids))}")
    for warning in data["warnings"]:
        click.secho(f"Warning: {format_error(warning)}", fg="yellow", err=True)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@planning.command("import")
@click.argument("project_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def planning_import(project_id, file, dry_run, as_json):
    """Add, update and delete milestones and planned work from a YAML or JSON
    file

    Entries with an ID (see `wb planning context`) are updated, only their
    given fields; others are added. delete_milestones and delete_planned_work
    list the IDs to delete."""
    data = request(
        "POST",
        f"projects/{project_id}/planning/import/",
        params={"dry_run": format_bool(dry_run)},
        json=load(file),
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@planning.group("work")
def planned_work():
    """Add, change and delete single planned work"""


def _work_options(fn):
    for option in reversed([
        click.option("--title"),
        click.option("--user", help="Short name.", shell_complete=complete_short_names),
        click.option("--service-type", help="Title of the service type."),
        click.option("--offer", help="Offer code, e.g. 2026-0042-o01."),
        click.option("--milestone", type=int, help="Milestone ID."),
        click.option(
            "--week",
            "weeks",
            multiple=True,
            type=click.DateTime(formats=["%Y-%m-%d"]),
            help="A day of a week of the work, can be repeated.",
        ),
        click.option("--hours", "planned_hours", type=float, help="Total hours."),
        click.option("--provisional/--definitive", "is_provisional", default=None),
        click.option("--notes", help="The text, or - to read it from stdin."),
    ]):
        fn = option(fn)
    return fn


def _work_data(file, **values):
    """The planned work from the YAML or JSON file, the options override it"""
    data = load(file) if file else {}
    if not isinstance(data, dict):
        terminate("The file has to contain a single planned work entry.")
    if values.get("notes") is not None:
        values["notes"] = text_or_stdin(values["notes"])
    if values.get("weeks"):
        values["weeks"] = [week.date().isoformat() for week in values["weeks"]]
    return data | {
        key: value for key, value in values.items() if value is not None and value != ()
    }


@planned_work.command("add")
@click.argument("project_id", type=int)
@click.argument("file", type=click.File("r"), required=False)
@_work_options
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def add_work(project_id, file, dry_run, as_json, **values):
    """Add planned work to a project, provisional by default

    Read from a YAML or JSON file (like an entry of `wb planning import`) or
    given with options, which override the file."""
    data = request(
        "POST",
        f"projects/{project_id}/planning/work/",
        params={"dry_run": format_bool(dry_run)},
        json=_work_data(file, **values),
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@planned_work.command("update")
@click.argument("work_id", type=int)
@click.argument("file", type=click.File("r"), required=False)
@_work_options
@click.option("--clear-offer", is_flag=True, help="Remove the offer.")
@click.option("--clear-milestone", is_flag=True, help="Remove the milestone.")
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_work(
    work_id, file, clear_offer, clear_milestone, dry_run, as_json, **values
):
    """Change planned work, only the given fields

    E.g. `wb planning work update 123 --definitive` once the customer has
    decided."""
    data = _work_data(file, **values)
    for flag, field in [(clear_offer, "offer"), (clear_milestone, "milestone")]:
        if flag and data.get(field) is not None:
            terminate(f"--clear-{field} and --{field} contradict each other.")
        if flag:
            data[field] = None
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"planning/work/{work_id}/",
        params={"dry_run": format_bool(dry_run)},
        json=data,
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@planned_work.command("delete")
@click.argument("work_id", type=int)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def delete_work(work_id, dry_run, as_json):
    """Delete planned work"""
    data = request(
        "DELETE",
        f"planning/work/{work_id}/",
        params={"dry_run": format_bool(dry_run)},
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)
