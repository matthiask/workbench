"""Organizations and people"""

import click

from wb.core import (
    _bool,
    _echo_fields,
    _echo_json,
    _echo_more,
    _link,
    _load,
    _page_options,
    _page_params,
    _request,
    _table,
    cli,
    console,
)


@cli.group()
def contacts():
    """Search organizations and people"""


@contacts.command("search")
@click.argument("query", nargs=-1, required=True)
@click.option("--all", "include_archived", is_flag=True, help="Include archived.")
@_page_options
@click.option("--json", "as_json", is_flag=True)
def search_contacts(query, include_archived, limit, offset, as_json):
    """Search organizations and people"""
    params = {"q": " ".join(query), "include_archived": _bool(include_archived)}
    organizations = _request(
        "GET", "contacts/organizations/", params=params | _page_params(limit, offset)
    )
    people = _request(
        "GET", "contacts/people/", params=params | _page_params(limit, offset)
    )
    if as_json:
        _echo_json({"organizations": organizations, "people": people})
        return
    table = _table("ID>", "Organization", title="Organizations")
    for organization in organizations["items"]:
        url = organization["url"]
        table.add_row(
            _link(organization["id"], url),
            _link(organization["name"], url)
            + (" (archived)" if organization["is_archived"] else ""),
        )
    console.print(table)
    _echo_more(organizations, offset, "organizations")
    table = _table("ID>", "Name", "Organization ID>", "Organization", title="People")
    for person in people["items"]:
        organization = person["organization"] or {}
        table.add_row(
            _link(person["id"], person["url"]),
            _link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
            _link(organization.get("id", ""), organization.get("url")),
            _link(organization.get("name", ""), organization.get("url")),
        )
    console.print(table)
    _echo_more(people, offset, "people")


@cli.group()
def organizations():
    """Look at organizations, search them with `wb contacts search`"""


@organizations.command("show")
@click.argument("organization_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_organization(organization_id, as_json):
    """Show an organization and its people"""
    data = _request("GET", f"contacts/organizations/{organization_id}/")
    if as_json:
        _echo_json(data)
        return
    _echo_fields(
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
    table = _table("ID>", "Name", title="People")
    for person in data["people"]:
        table.add_row(
            _link(person["id"], person["url"]),
            _link(person["full_name"], person["url"])
            + (" (archived)" if person["is_archived"] else ""),
        )
    console.print(table)


@cli.group()
def people():
    """Look at and add people, search them with `wb contacts search`"""


@people.command("show")
@click.argument("person_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_person(person_id, as_json):
    """Show a person and their contact details"""
    data = _request("GET", f"contacts/people/{person_id}/")
    _echo_json(data) if as_json else _echo_person(data)


@people.command("context")
def people_context():
    """Print the schema of a person to create

    Feed this to an LLM together with an email signature, a business card
    or whatever you've got."""
    _echo_json(_request("GET", "contacts/people/context/"))


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
    data = _request(
        "POST",
        "contacts/people/",
        params={
            "dry_run": _bool(dry_run),
            "allow_duplicates": _bool(allow_duplicates),
        },
        json=_load(file),
    )
    if as_json:
        _echo_json(data)
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
    data = _request(
        "POST",
        f"contacts/people/{person_id}/details/",
        params={"dry_run": _bool(dry_run)},
        json=_load(file),
    )
    if as_json:
        _echo_json(data)
        return
    _echo_person(data)
    if dry_run:
        console.print("Dry run, nothing has been saved.")


def _echo_person(data):
    organization = data["organization"] or {}
    _echo_fields(
        data["full_name"] + (" (archived)" if data["is_archived"] else ""),
        [
            ("ID", data["id"]),
            (
                "Organization",
                _link(organization.get("name", ""), organization.get("url")),
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
