"""Organizations and people"""

import click

from wb.core import (
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_fields,
    echo_json,
    echo_more,
    format_bool,
    link,
    load,
    make_table,
    page_options,
    page_params,
    request,
    terminate,
)


@cli.group()
def contacts():
    """Search organizations and people"""


@contacts.command("search")
@click.argument("query", nargs=-1, required=True)
@click.option("--all", "include_archived", is_flag=True, help="Include archived.")
@page_options
@click.option("--json", "as_json", is_flag=True)
def search_contacts(query, include_archived, limit, offset, as_json):
    """Search organizations and people"""
    params = {"q": " ".join(query), "include_archived": format_bool(include_archived)}
    organizations = request(
        "GET", "contacts/organizations/", params=params | page_params(limit, offset)
    )
    people = request(
        "GET", "contacts/people/", params=params | page_params(limit, offset)
    )
    if as_json:
        echo_json({"organizations": organizations, "people": people})
        return
    table = make_table("ID>", "Organization", title="Organizations")
    for organization in organizations["items"]:
        url = organization["url"]
        table.add_row(
            link(organization["id"], url),
            link(organization["name"], url)
            + (" (archived)" if organization["is_archived"] else ""),
        )
    console.print(table)
    echo_more(organizations, offset, "organizations")
    table = make_table(
        "ID>", "Name", "Organization ID>", "Organization", title="People"
    )
    for person in people["items"]:
        organization = person["organization"] or {}
        table.add_row(
            link(person["id"], person["url"]),
            link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
            link(organization.get("id", ""), organization.get("url")),
            link(organization.get("name", ""), organization.get("url")),
        )
    console.print(table)
    echo_more(people, offset, "people")


@cli.group()
def organizations():
    """Look at organizations, search them with `wb contacts search`"""


@organizations.command("show")
@click.argument("organization_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_organization(organization_id, as_json):
    """Show an organization and its people"""
    data = request("GET", f"contacts/organizations/{organization_id}/")
    if as_json:
        echo_json(data)
        return
    echo_fields(
        data["name"] + (" (archived)" if data["is_archived"] else ""),
        [
            ("ID", data["id"]),
            ("Primary contact", data["primary_contact"]),
            ("Groups", ", ".join(data["groups"])),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["notes"]:
        console.print()
        console.print(data["notes"])
    table = make_table("ID>", "Name", title="People")
    for person in data["people"]:
        table.add_row(
            link(person["id"], person["url"]),
            link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
        )
    console.print(table)


@cli.group()
def people():
    """Look at, search and add people"""


@people.command("search")
@click.argument("query", nargs=-1)
@click.option("--organization", type=int, help="Organization ID.")
@click.option(
    "--group",
    help="ID or title of a group, also people in it through their organization.",
)
@click.option("--without-groups", is_flag=True, help="Only people in no active group.")
@click.option(
    "--primary-contact", help="Short name.", shell_complete=complete_short_names
)
@click.option(
    "--projects-or-deals-since",
    type=click.DateTime(["%Y-%m-%d"]),
    help="Only contacts of projects or deals created since the date.",
)
@click.option("--all", "include_archived", is_flag=True, help="Include archived.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_people(
    query,
    organization,
    group,
    without_groups,
    primary_contact,
    projects_or_deals_since,
    include_archived,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search people, e.g. the members of a group or people without any
    group like the list of people in the web interface"""
    params = {
        "q": " ".join(query),
        "include_archived": format_bool(include_archived),
        "without_groups": format_bool(without_groups),
    }
    if organization:
        params["organization"] = organization
    if group:
        params["group"] = group
    if primary_contact:
        params["primary_contact"] = primary_contact
    if projects_or_deals_since:
        params["projects_or_deals_since"] = projects_or_deals_since.date().isoformat()
    data = request(
        "GET", "contacts/people/", params=params | page_params(limit, offset)
    )
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Name", "Organization", "Groups", "Primary contact")
    for person in data["items"]:
        organization = person["organization"] or {}
        table.add_row(
            link(person["id"], person["url"]),
            link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
            link(organization.get("name", ""), organization.get("url")),
            ", ".join(person["groups"]),
            person["primary_contact"],
        )
    console.print(table)
    echo_more(data, offset, "people")


@people.command("show")
@click.argument("person_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_person(person_id, as_json):
    """Show a person and their contact details"""
    data = request("GET", f"contacts/people/{person_id}/")
    echo_json(data) if as_json else _echo_person(data)


@people.command("update")
@click.argument("person_id", type=int)
@click.option(
    "--primary-contact", help="Short name.", shell_complete=complete_short_names
)
@click.option(
    "--add-group",
    "add_groups",
    multiple=True,
    help="ID or title of a group; repeat it for several. Groups which apply to"
    " organizations are added to the organization.",
)
@click.option(
    "--remove-group",
    "remove_groups",
    multiple=True,
    help="ID or title of a group; repeat it for several.",
)
@click.option(
    "--archive/--unarchive", "is_archived", default=None, help="E.g. who left."
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_person(
    person_id, primary_contact, add_groups, remove_groups, is_archived, dry_run, as_json
):
    """Change the primary contact and the groups of a person or archive them,
    like in the web interface"""
    data = {
        key: value
        for key, value in [
            ("primary_contact", primary_contact),
            ("add_groups", list(add_groups)),
            ("remove_groups", list(remove_groups)),
            ("is_archived", is_archived),
        ]
        if value not in (None, [])
    }
    if not data:
        terminate(
            "Nothing to change, pass --primary-contact, --add-group,"
            " --remove-group, --archive or --unarchive."
        )
    data = request(
        "PATCH",
        f"contacts/people/{person_id}/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing changed:")
    _echo_person(data)


@people.command("context")
def people_context():
    """Print the schema of a person to create

    Feed this to an LLM together with an email signature, a business card
    or whatever you've got."""
    echo_json(request("GET", "contacts/people/context/"))


@people.command("create")
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option(
    "--allow-duplicates",
    is_flag=True,
    help="Create the person (and the organization) even if the name exists already.",
)
@click.option("--json", "as_json", is_flag=True)
def create_person(file, dry_run, allow_duplicates, as_json):
    """Create a person with their contact details from a YAML or JSON file

    Search for the person and their organization with `wb contacts search`
    first. Email addresses which are already in use are always rejected."""
    data = request(
        "POST",
        "contacts/people/",
        params={
            "dry_run": format_bool(dry_run),
            "allow_duplicates": format_bool(allow_duplicates),
        },
        json=load(file),
    )
    if as_json:
        echo_json(data)
        return
    _echo_person(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


@people.command("add-details")
@click.argument("person_id", type=int)
@click.argument("file", type=click.File("r"))
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def add_person_details(person_id, file, dry_run, as_json):
    """Add email addresses, phone numbers and postal addresses to a person

    The YAML or JSON file contains email_addresses, phone_numbers and
    postal_addresses like for `wb people create`. Existing details are never
    changed or removed."""
    data = request(
        "POST",
        f"contacts/people/{person_id}/details/",
        params={"dry_run": format_bool(dry_run)},
        json=load(file),
    )
    if as_json:
        echo_json(data)
        return
    _echo_person(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


def _echo_person(data):
    organization = data["organization"] or {}
    echo_fields(
        data["full_name"] + (" (archived)" if data["is_archived"] else ""),
        [
            ("ID", data["id"]),
            (
                "Organization",
                link(organization.get("name", ""), organization.get("url")),
            ),
            ("Organization ID", organization.get("id")),
            ("Salutation", data["salutation"]),
            ("Primary contact", data["primary_contact"]),
            ("Groups", ", ".join(data["groups"])),
            *(
                (f"{label} ({detail['type']})", detail["value"])
                for label, key in [
                    ("Email", "email_addresses"),
                    ("Phone", "phone_numbers"),
                    ("Address", "postal_addresses"),
                ]
                for detail in data[key]
            ),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["notes"]:
        console.print()
        console.print(data["notes"])


@cli.group(invoke_without_command=True)
@click.pass_context
def groups(ctx):
    """Find, create and archive groups of people, e.g. for mailings

    Without a command, lists the active groups."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_groups)


@groups.command("search")
@click.argument("query", nargs=-1)
@click.option("--archived", "status", flag_value="archived", help="Only archived.")
@click.option("--all", "status", flag_value="all", help="Include archived.")
@page_options
@click.option("--json", "as_json", is_flag=True)
def search_groups(query, status, limit, offset, as_json):
    """Search groups with their active people and organizations"""
    params = {"q": " ".join(query), "s": status or ""}
    data = request(
        "GET", "contacts/groups/", params=params | page_params(limit, offset)
    )
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Group", "People>", "Organizations>")
    for group in data["items"]:
        notes = [
            note
            for note, flag in [
                ("applies to organizations", group["applies_to_organizations"]),
                ("archived", group["is_archived"]),
            ]
            if flag
        ]
        table.add_row(
            link(group["id"], group["url"]),
            group["title"] + (f" ({', '.join(notes)})" if notes else ""),
            str(group["people_count"]),
            str(group["organizations_count"]),
            style="dim" if group["is_archived"] else None,
        )
    console.print(table)
    echo_more(data, offset, "groups")


def _echo_group(data, *, dry_run):
    prefix = "Dry run, nothing changed: " if dry_run else ""
    notes = [
        note
        for note, flag in [
            ("applies to organizations", data["applies_to_organizations"]),
            ("archived", data["is_archived"]),
        ]
        if flag
    ]
    console.print(
        f"{prefix}{link(data['id'], data['url'])} {data['title']}"
        + (f" ({', '.join(notes)})" if notes else "")
    )


@groups.command("create")
@click.argument("title")
@click.option(
    "--applies-to-organizations",
    is_flag=True,
    help="E.g. industries: people are in it through their organization.",
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_group(title, applies_to_organizations, dry_run, as_json):
    """Create a group, titles are unique"""
    data = request(
        "POST",
        "contacts/groups/",
        json={"title": title, "applies_to_organizations": applies_to_organizations},
        params={"dry_run": format_bool(dry_run)},
    )
    echo_json(data) if as_json else _echo_group(data, dry_run=dry_run)


@groups.command("update")
@click.argument("group_id", type=int)
@click.option("--title")
@click.option(
    "--archive/--unarchive",
    "is_archived",
    default=None,
    help="People only in archived groups are archived after five years without use.",
)
@click.option(
    "--applies-to-organizations/--applies-to-people",
    "applies_to_organizations",
    default=None,
    help="Applying to organizations moves the memberships to the organizations.",
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_group(
    group_id, title, is_archived, applies_to_organizations, dry_run, as_json
):
    """Rename or archive a group"""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("is_archived", is_archived),
            ("applies_to_organizations", applies_to_organizations),
        ]
        if value is not None
    }
    if not data:
        terminate(
            "Nothing to change, pass --title, --archive, --unarchive,"
            " --applies-to-organizations or --applies-to-people."
        )
    data = request(
        "PATCH",
        f"contacts/groups/{group_id}/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    echo_json(data) if as_json else _echo_group(data, dry_run=dry_run)
