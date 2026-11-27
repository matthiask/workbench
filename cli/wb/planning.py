"""Planning"""

import csv
import datetime as dt
import sys

import click

from wb.core import (
    change_options,
    change_params,
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
@click.option("--campaign", type=int, help="Campaign ID, see `wb campaigns`.")
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
        "milestone_id",
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
            work["milestone_id"] or "",
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
        "ID>",
        "Project",
        "Offer",
        "Milestone",
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
            str(work["id"]),
            link(project["code"], project["url"]),
            work["offer"]["code"] if work["offer"] else "",
            f"{work['milestone']} ({work['milestone_id']})"
            if work["milestone"]
            else "",
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
        table = make_table(
            "ID>", "Date", "Project", "Milestone", "Hours>", title="Milestones"
        )
        for milestone in data["milestones"]:
            table.add_row(
                str(milestone["id"]),
                milestone["date"],
                link(milestone["project"]["code"], milestone["project"]["url"]),
                link(milestone["title"], milestone["url"]),
                format_hours(milestone["estimated_total_hours"]),
            )
        console.print(table)
    if data["external_work"]:
        table = make_table(
            "ID>",
            "Project",
            "Title",
            "Provided by",
            "First week",
            "Last week",
            title="External work",
        )
        for work in data["external_work"]:
            table.add_row(
                str(work["id"]),
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
        "Milestone",
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
            f"{pw['milestone']} ({pw['milestone_id']})" if pw.get("milestone") else "",
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
        table = make_table(
            "ID>", "Milestone", "Date", "Phase starts on", "Estimated hours>"
        )
        for milestone in data["milestones"]:
            table.add_row(
                str(milestone["id"] or "(new)"),
                milestone["title"],
                milestone["date"],
                milestone["phase_starts_on"] or "",
                milestone["estimated_total_hours"],
            )
        console.print(table)
    if data["planned_work"]:
        _echo_planned_work(data["planned_work"])
    if data.get("external_work"):
        table = make_table(
            "ID>", "External work", "Provided by", "Service type", "Milestone", "Weeks"
        )
        for ew in data["external_work"]:
            weeks = ew["weeks"]
            table.add_row(
                str(ew["id"] or "(new)"),
                ew["title"],
                ew["provided_by"],
                ew["service_type"] or "",
                f"{ew['milestone']} ({ew['milestone_id']})" if ew["milestone"] else "",
                f"{weeks[0]} – {weeks[-1]} ({len(weeks)})"
                if len(weeks) > 1
                else weeks[0],
            )
        console.print(table)
    for key, what in [
        ("deleted_milestones", "milestones"),
        ("deleted_planned_work", "planned work"),
        ("deleted_external_work", "external work"),
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
        click.option(
            "--service-type",
            help="Title of the service type, see `wb services types`.",
        ),
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


def _batch_selection(project, campaign, period, since, until, users, team):
    """The planned work selected by the export's filters, from this week on
    by default"""
    if not (project or campaign or users or team):
        terminate(
            "Select planned work with --work, --user, --team, --project or --campaign."
        )
    if not period and not until:
        since = since or dt.datetime.combine(dt.date.today(), dt.time())
        until = since + dt.timedelta(days=3652)  # The export's maximum
    params = period_params(period, since, until, users=users, team=team)
    if project:
        params["project"] = project
    if campaign:
        params["campaign"] = campaign
    return request("GET", "planning/export/", params=params)


def _echo_selection(data):
    table = make_table(
        "ID>",
        "Project",
        "Planned work",
        "User",
        "First week",
        "Last week",
        "Hours>",
        title="Selected planned work",
    )
    for work in data["planned_work"]:
        table.add_row(
            str(work["id"]),
            link(work["project"]["code"], work["project"]["url"]),
            link(work["title"], work["url"]),
            work["user"],
            work["weeks"][0],
            work["weeks"][-1],
            format_hours(work["planned_hours"]),
        )
    console.print(table)
    since = dt.date.fromisoformat(data["since"])
    since -= dt.timedelta(days=since.weekday())
    if earlier := [w for w in data["planned_work"] if w["weeks"][0] < str(since)]:
        console.print(
            f"{len(earlier)} of them also have weeks before {since}, the"
            " changes apply to all of their weeks.",
            style="yellow",
        )


@planned_work.command("batch")
@click.option(
    "--work",
    "work_ids",
    type=int,
    multiple=True,
    help="ID of planned work, can be repeated; instead of the filters.",
)
@click.option("--project", type=int, help="Select the work of this project (ID).")
@click.option(
    "--campaign", type=int, help="Select the work of this campaign's projects (ID)."
)
@period_options("defaults to the work from this week on")
@users_options
@click.option(
    "--assign-to",
    help="Short name of an active user.",
    shell_complete=complete_short_names,
)
@click.option("--move-by-weeks", type=int, default=0, help="Can be negative.")
@click.option(
    "--move-to-project",
    help="ID or code of an open project; removes the offer and the milestone.",
)
@click.option("--provisional/--definitive", default=None)
@click.option("--delete", is_flag=True, help="Delete the selected work.")
@change_options()
def batch_work(
    work_ids,
    project,
    campaign,
    period,
    since,
    until,
    users,
    team,
    assign_to,
    move_by_weeks,
    move_to_project,
    provisional,
    delete,
    dry_run,
    ignore_warnings,
    as_json,
):
    """Change or delete planned work of any projects at once

    Selects the work with the filters of `wb planning export` (the work
    from this week on by default) or with --work, e.g. to hand over the
    future work of someone who leaves:
    `wb planning work batch --user ub --since 2026-12-07 --assign-to aha`.
    Work overlapping the start of the period is changed as a whole."""
    filters = (project, campaign, period, since, until, users, team)
    if work_ids and any(filters):
        terminate("Select planned work either with --work or with filters.")
    changes = {
        "assign_to": assign_to,
        "move_by_weeks": move_by_weeks or None,
        "project": move_to_project,
        "provisional": provisional,
    }
    changes = {key: value for key, value in changes.items() if value is not None}
    if delete and changes:
        terminate("--delete and changes contradict each other.")
    if not delete and not changes:
        terminate("Nothing to change.")
    if not work_ids:
        selection = _batch_selection(*filters)
        if not selection["planned_work"]:
            console.print("No planned work selected.")
            return
        if not as_json:
            _echo_selection(selection)
        work_ids = [work["id"] for work in selection["planned_work"]]
    data = request(
        "POST",
        "planning/work/batch/",
        params=change_params(dry_run, ignore_warnings),
        json={"work": list(work_ids), "delete": delete} | changes,
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


def _changes(**values):
    """The given options; - reads the notes from stdin, dates as strings"""
    changes = {}
    for key, value in values.items():
        if value is None or value == ():
            continue
        if key == "notes":
            changes[key] = text_or_stdin(value)
        elif key == "weeks":
            changes[key] = [week.date().isoformat() for week in value]
        elif isinstance(value, dt.datetime):
            changes[key] = value.date().isoformat()
        else:
            changes[key] = value
    return changes


def _clear(changes, flags):
    """``--clear-FIELD`` flags set the field to null"""
    for field, flag in flags.items():
        option = field.replace("_", "-")
        if flag and changes.get(field) is not None:
            terminate(f"--clear-{option} and --{option} contradict each other.")
        if flag:
            changes[field] = None
    if not changes:
        terminate("Nothing to change.")
    return changes


DATE = click.DateTime(formats=["%Y-%m-%d"])


@planning.group("milestones")
def milestones():
    """Add, change and delete milestones"""


def _milestone_options(fn):
    for option in reversed([
        click.option("--date", type=DATE, help="The day of the milestone."),
        click.option("--phase-starts-on", type=DATE),
        click.option(
            "--hours",
            "estimated_total_hours",
            type=float,
            help="Planned hours, 0 by default.",
        ),
        click.option(
            "--color",
            help="Color of its planned work: #e03131 (red), #f76707 (orange),"
            " #fcc419 (yellow), #37b24d (green), #1098ad (cyan), #3b5bdb (blue),"
            " #7048e8 (violet) or #d6336c (pink).",
        ),
    ]):
        fn = option(fn)
    return fn


@milestones.command("create")
@click.argument("project_id", type=int)
@click.argument("title")
@_milestone_options
@change_options()
def create_milestone(project_id, title, dry_run, ignore_warnings, as_json, **values):
    """Add a milestone to a project

    E.g. `wb planning milestones create 1234 Launch --date 2027-03-01`."""
    data = request(
        "POST",
        f"projects/{project_id}/planning/milestones/",
        params=change_params(dry_run, ignore_warnings),
        json={"title": title} | _changes(**values),
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@milestones.command("update")
@click.argument("milestone_id", type=int)
@click.option("--title")
@_milestone_options
@click.option("--clear-phase-starts-on", is_flag=True)
@click.option("--clear-color", is_flag=True, help="Use the service type's color.")
@change_options()
def update_milestone(
    milestone_id,
    clear_phase_starts_on,
    clear_color,
    dry_run,
    ignore_warnings,
    as_json,
    **values,
):
    """Change a milestone, only the given fields"""
    changes = _clear(
        _changes(**values),
        {"phase_starts_on": clear_phase_starts_on, "color": clear_color},
    )
    data = request(
        "PATCH",
        f"planning/milestones/{milestone_id}/",
        params=change_params(dry_run, ignore_warnings),
        json=changes,
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@milestones.command("delete")
@click.argument("milestone_id", type=int)
@change_options(warnings=False)
def delete_milestone(milestone_id, dry_run, as_json):
    """Delete a milestone, its planned and external work stay without it"""
    data = request(
        "DELETE",
        f"planning/milestones/{milestone_id}/",
        params=change_params(dry_run),
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@planning.group("external-work")
def external_work():
    """Add, change and delete external work"""


def _external_work_options(fn):
    for option in reversed([
        click.option(
            "--provided-by",
            type=int,
            help="Organization ID, new work defaults to the customer.",
        ),
        click.option(
            "--service-type",
            help="Title of the service type, see `wb services types`.",
        ),
        click.option("--milestone", type=int, help="Milestone ID."),
        click.option(
            "--week",
            "weeks",
            multiple=True,
            type=DATE,
            help="A day of a week of the work, can be repeated; new work"
            " defaults to this week.",
        ),
        click.option("--notes", help="The text, or - to read it from stdin."),
    ]):
        fn = option(fn)
    return fn


@external_work.command("create")
@click.argument("project_id", type=int)
@click.argument("title")
@_external_work_options
@change_options()
def create_external_work(
    project_id, title, dry_run, ignore_warnings, as_json, **values
):
    """Add external work (e.g. by the customer or a freelancer) to a project"""
    data = request(
        "POST",
        f"projects/{project_id}/planning/external-work/",
        params=change_params(dry_run, ignore_warnings),
        json={"title": title} | _changes(**values),
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@external_work.command("update")
@click.argument("work_id", type=int)
@click.option("--title")
@_external_work_options
@click.option("--clear-service-type", is_flag=True)
@click.option("--clear-milestone", is_flag=True)
@change_options()
def update_external_work(
    work_id,
    clear_service_type,
    clear_milestone,
    dry_run,
    ignore_warnings,
    as_json,
    **values,
):
    """Change external work, only the given fields"""
    changes = _clear(
        _changes(**values),
        {"service_type": clear_service_type, "milestone": clear_milestone},
    )
    data = request(
        "PATCH",
        f"planning/external-work/{work_id}/",
        params=change_params(dry_run, ignore_warnings),
        json=changes,
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)


@external_work.command("delete")
@click.argument("work_id", type=int)
@change_options(warnings=False)
def delete_external_work(work_id, dry_run, as_json):
    """Delete external work"""
    data = request(
        "DELETE",
        f"planning/external-work/{work_id}/",
        params=change_params(dry_run),
    )
    _echo_import_result(data, dry_run=dry_run, as_json=as_json)
