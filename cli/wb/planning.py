"""Planning"""

import csv
import sys

import click

from wb.core import (
    cli,
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


@planning.command("import")
@click.argument("project_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def planning_import(project_id, file, dry_run, as_json):
    """Add milestones and planned work from a YAML or JSON file"""
    data = request(
        "POST",
        f"projects/{project_id}/planning/import/",
        params={"dry_run": format_bool(dry_run)},
        json=load(file),
    )
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
    table = make_table(
        "Planned work",
        "User",
        "Service type",
        "Offer",
        "Weeks",
        "Hours>",
        "Provisional",
    )
    for pw in data["planned_work"]:
        weeks = pw["weeks"]
        table.add_row(
            pw["title"],
            pw["user"],
            pw["service_type"],
            pw["offer"] or "",
            f"{weeks[0]} – {weeks[-1]} ({len(weeks)})" if len(weeks) > 1 else weeks[0],
            pw["planned_hours"],
            "yes" if pw["is_provisional"] else "",
        )
    console.print(table)
    for warning in data["warnings"]:
        click.secho(f"Warning: {format_error(warning)}", fg="yellow", err=True)
    if dry_run:
        console.print("Dry run, nothing has been saved.")
