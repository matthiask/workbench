"""Organizations and people"""

import click
from rich.text import Text

from wb.core import (
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_fields,
    echo_json,
    echo_more,
    format_bool,
    ignore_warnings_option,
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
@click.option("--include-archived", is_flag=True, help="Also archived contacts.")
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
    """Look at, search, change and merge organizations"""


@organizations.command("search")
@click.argument("query", nargs=-1)
@click.option(
    "--without-active-people",
    is_flag=True,
    help="Only organizations without active people.",
)
@click.option(
    "--primary-contact", help="Short name.", shell_complete=complete_short_names
)
@click.option(
    "--several-postal-addresses",
    is_flag=True,
    help="Only organizations whose active people have different postal addresses,"
    " private ones (e.g. Home) don't count.",
)
@click.option("--include-archived", is_flag=True, help="Also archived contacts.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_organizations(
    query,
    without_active_people,
    primary_contact,
    several_postal_addresses,
    include_archived,
    limit,
    offset,
    as_csv,
    as_json,
):
    """Search organizations"""
    params = {
        "q": " ".join(query),
        "include_archived": format_bool(include_archived),
        "without_active_people": format_bool(without_active_people),
        "several_postal_addresses": format_bool(several_postal_addresses),
    }
    if primary_contact:
        params["primary_contact"] = primary_contact
    data = request(
        "GET", "contacts/organizations/", params=params | page_params(limit, offset)
    )
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Organization")
    for organization in data["items"]:
        url = organization["url"]
        table.add_row(
            link(organization["id"], url),
            link(organization["name"], url)
            + (" (archived)" if organization["is_archived"] else ""),
        )
    console.print(table)
    echo_more(data, offset, "organizations")


def _echo_organization(data):
    echo_fields(
        data["name"] + (" (archived)" if data["is_archived"] else ""),
        [
            ("ID", data["id"]),
            ("Primary contact", data["primary_contact"]),
            ("Email address", data["email"]),
            ("Accounts payable", data["accounts_payable_email"]),
            ("Phone number", data["phone_number"]),
            ("Billing address", data["default_billing_address"]),
            ("Private person", "yes" if data["is_private_person"] else ""),
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
    if data["postal_addresses"]:
        table = make_table(
            "ID>", "Postal address", "Type", "People", title="Postal addresses"
        )
        for address in data["postal_addresses"]:
            table.add_row(
                str(address["id"]),
                address["value"],
                ", ".join(address.get("types", [])),
                ", ".join(
                    f"{person['full_name']} ({person['id']})"
                    for person in address["people"]
                ),
            )
        console.print(table)


@organizations.command("show")
@click.argument("organization_id", type=int)
@click.option("--json", "as_json", is_flag=True)
def show_organization(organization_id, as_json):
    """Show an organization and its people"""
    data = request("GET", f"contacts/organizations/{organization_id}/")
    echo_json(data) if as_json else _echo_organization(data)


@organizations.command("create")
@click.argument("name")
@click.option("--private-person", "is_private_person", is_flag=True)
@click.option("--notes")
@click.option(
    "--primary-contact",
    help="Short name, defaults to you.",
    shell_complete=complete_short_names,
)
@click.option(
    "--email",
    default="",
    help="Central address, e.g. info@, shown on the organization's people too.",
)
@click.option(
    "--accounts-payable-email",
    default="",
    help="For invoices and payment reminders.",
)
@click.option(
    "--phone-number",
    default="",
    help="Central number, e.g. the reception, shown on the organization's people too.",
)
@click.option(
    "--default-billing-address",
    default="",
    help="E.g. of a centralized accounts payable department.",
)
@click.option(
    "--group",
    "groups",
    multiple=True,
    help="Title or ID of a group; repeat it for several.",
)
@click.option(
    "--allow-duplicates",
    is_flag=True,
    help="Create it although an organization with the same name exists.",
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def create_organization(
    name,
    is_private_person,
    notes,
    primary_contact,
    email,
    accounts_payable_email,
    phone_number,
    default_billing_address,
    groups,
    allow_duplicates,
    dry_run,
    as_json,
):
    """Create an organization; people are added to it with `wb people create`
    and its ID. Organizations with the same name are rejected."""
    data = {
        "name": name,
        "is_private_person": is_private_person,
        "notes": notes or "",
        "email": email,
        "accounts_payable_email": accounts_payable_email,
        "phone_number": phone_number,
        "default_billing_address": default_billing_address,
        "groups": list(groups),
    }
    if primary_contact:
        data["primary_contact"] = primary_contact
    data = request(
        "POST",
        "contacts/organizations/",
        json=data,
        params={
            "dry_run": format_bool(dry_run),
            "allow_duplicates": format_bool(allow_duplicates),
        },
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing created:")
    _echo_organization(data)


@organizations.command("update")
@click.argument("organization_id", type=int)
@click.option("--name")
@click.option("--private-person/--no-private-person", "is_private_person", default=None)
@click.option("--notes", help="Replaces the notes; an empty string removes them.")
@click.option(
    "--primary-contact", help="Short name.", shell_complete=complete_short_names
)
@click.option(
    "--email",
    help="Central address, e.g. info@, shown on the organization's people too;"
    " an empty string removes it.",
)
@click.option(
    "--accounts-payable-email",
    help="For invoices and payment reminders; an empty string removes it.",
)
@click.option(
    "--phone-number",
    help="Central number, e.g. the reception, shown on the organization's"
    " people too; an empty string removes it.",
)
@click.option(
    "--default-billing-address",
    help="E.g. of a centralized accounts payable department; an empty string"
    " removes it.",
)
@click.option(
    "--add-group",
    "add_groups",
    multiple=True,
    help="Title or ID of a group; repeat it for several.",
)
@click.option(
    "--remove-group",
    "remove_groups",
    multiple=True,
    help="Title or ID of a group; repeat it for several.",
)
@click.option(
    "--archive/--unarchive",
    "is_archived",
    default=None,
    help="Archiving warns about active people (archive-people), ignoring the"
    " warning archives them too.",
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@ignore_warnings_option
@click.option("--json", "as_json", is_flag=True)
def update_organization(
    organization_id,
    name,
    is_private_person,
    notes,
    primary_contact,
    email,
    accounts_payable_email,
    phone_number,
    default_billing_address,
    add_groups,
    remove_groups,
    is_archived,
    dry_run,
    ignore_warnings,
    as_json,
):
    """Change the name, the notes, the primary contact, the email addresses,
    the phone number, the billing address and the groups of an organization
    or archive it"""
    data = {
        key: value
        for key, value in [
            ("name", name),
            ("is_private_person", is_private_person),
            ("notes", notes),
            ("primary_contact", primary_contact),
            ("email", email),
            ("accounts_payable_email", accounts_payable_email),
            ("phone_number", phone_number),
            ("default_billing_address", default_billing_address),
            ("add_groups", list(add_groups)),
            ("remove_groups", list(remove_groups)),
            ("is_archived", is_archived),
        ]
        if value not in (None, [])
    }
    if not data:
        terminate("Nothing to change, see --help for the options.")
    data = request(
        "PATCH",
        f"contacts/organizations/{organization_id}/",
        json=data,
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing changed:")
    _echo_organization(data)


@organizations.command("change-address")
@click.argument("organization_id", type=int)
@click.option(
    "--address",
    "address_id",
    type=int,
    required=True,
    help="ID of the address from `wb organizations show`.",
)
@click.option("--street")
@click.option("--house-number")
@click.option("--address-suffix")
@click.option("--postal-code")
@click.option("--city")
@click.option("--country", help="ISO 3166-1 code, e.g. CH.")
@click.option("--override", help="Replaces the whole address if set.")
@click.option(
    "--person",
    "people",
    type=int,
    multiple=True,
    help="ID of a person whose address changes; repeat it for several. Defaults"
    " to everyone who has the address.",
)
@click.option("--dry-run", is_flag=True, help="Validate and show the result only.")
@click.option("--json", "as_json", is_flag=True)
def change_organization_address(
    organization_id,
    address_id,
    street,
    house_number,
    address_suffix,
    postal_code,
    city,
    country,
    override,
    people,
    dry_run,
    as_json,
):
    """Change a postal address of several people of an organization at once,
    e.g. when it moves; fields which aren't given stay"""
    data = {
        key: value
        for key, value in [
            ("street", street),
            ("house_number", house_number),
            ("address_suffix", address_suffix),
            ("postal_code", postal_code),
            ("city", city),
            ("country", country),
            ("postal_address_override", override),
        ]
        if value is not None
    }
    if not data:
        terminate("Nothing to change, pass the fields of the new address.")
    data["address"] = address_id
    if people:
        data["people"] = list(people)
    data = request(
        "POST",
        f"contacts/organizations/{organization_id}/postal-address/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing changed:")
    _echo_organization(data)


@organizations.command("merge")
@click.argument("organization_id", type=int)
@click.option("--into", type=int, required=True, help="ID of the organization to keep.")
@click.option("--dry-run", is_flag=True, help="Validate and show the result only.")
@click.option("--json", "as_json", is_flag=True)
def merge_organization(organization_id, into, dry_run, as_json):
    """Merge a duplicate into the organization to keep and delete it

    People, projects, deals, invoices and groups move. An inactive primary
    contact of the organization kept is replaced by the duplicate's active
    one."""
    data = request(
        "POST",
        f"contacts/organizations/{organization_id}/merge/",
        json={"into": into},
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    _echo_organization(data)
    console.print(
        f"Dry run, nothing changed: {organization_id} would be merged into {into}."
        if dry_run
        else f"{organization_id} has been merged into {into}."
    )


@cli.group()
def people():
    """Look at, search and add people"""


@people.command("search")
@click.argument("query", nargs=-1)
@click.option("--organization", type=int, help="Organization ID.")
@click.option(
    "--group",
    help="Title or ID of a group, also people in it through their organization.",
)
@click.option("--without-groups", is_flag=True, help="Only people in no active group.")
@click.option(
    "--missing-postal-address",
    is_flag=True,
    help="Only people without a postal address with street, postal code and city.",
)
@click.option(
    "--primary-contact", help="Short name.", shell_complete=complete_short_names
)
@click.option(
    "--projects-or-deals-since",
    type=click.DateTime(["%Y-%m-%d"]),
    help="Only contacts of projects or deals created since the date.",
)
@click.option("--include-archived", is_flag=True, help="Also archived contacts.")
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def search_people(
    query,
    organization,
    group,
    without_groups,
    missing_postal_address,
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
        "missing_postal_address": format_bool(missing_postal_address),
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
@click.option("--given-name")
@click.option("--family-name")
@click.option(
    "--address",
    help="Mr./Ms./... in the language of the correspondence, e.g. Herr or Frau;"
    " an empty string removes it.",
)
@click.option(
    "--salutation",
    help="Complete salutation in the language of the correspondence, e.g."
    " `Lieber Hans` or `Sehr geehrte Frau Muster`.",
)
@click.option(
    "--first-name-terms/--no-first-name-terms",
    "address_on_first_name_terms",
    default=None,
    help="Whether to address the person on first-name terms.",
)
@click.option("--notes", help="Replaces the notes; an empty string removes them.")
@click.option(
    "--primary-contact", help="Short name.", shell_complete=complete_short_names
)
@click.option(
    "--add-group",
    "add_groups",
    multiple=True,
    help="Title or ID of a group; repeat it for several. Groups which apply to"
    " organizations are added to the organization.",
)
@click.option(
    "--remove-group",
    "remove_groups",
    multiple=True,
    help="Title or ID of a group; repeat it for several. Groups which apply to"
    " organizations are removed from the organization, so all its people lose"
    " them.",
)
@click.option(
    "--remove-email",
    "remove_emails",
    multiple=True,
    help="Email address to remove, e.g. a generic one which belongs to the"
    " organization; repeat it for several.",
)
@click.option(
    "--remove-phone",
    "remove_phones",
    multiple=True,
    help="Phone number to remove, e.g. the reception which belongs to the"
    " organization; repeat it for several.",
)
@click.option(
    "--remove-postal-address",
    "remove_postal_addresses",
    type=int,
    multiple=True,
    help="ID of a postal address to remove (`wb people show`), e.g. an old one"
    " of the organization; repeat it for several.",
)
@click.option(
    "--email-type",
    "email_address_types",
    type=(int, str),
    multiple=True,
    metavar="ID TYPE",
    help="New type of an email address (`wb people show`), e.g. `Home`;"
    " repeat it for several.",
)
@click.option(
    "--phone-type",
    "phone_number_types",
    type=(int, str),
    multiple=True,
    metavar="ID TYPE",
    help="New type of a phone number (`wb people show`), e.g. `Mobile`;"
    " repeat it for several.",
)
@click.option(
    "--postal-address-type",
    "postal_address_types",
    type=(int, str),
    multiple=True,
    metavar="ID TYPE",
    help="New type of a postal address (`wb people show`), e.g. `home` for a"
    " private address saved as a work address; repeat it for several.",
)
@click.option(
    "--organization",
    help="ID of the organization, e.g. the new employer of someone who left;"
    " an empty string removes the person from their organization.",
)
@click.option(
    "--archive/--unarchive", "is_archived", default=None, help="E.g. who left."
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@ignore_warnings_option
@click.option("--json", "as_json", is_flag=True)
def update_person(
    person_id,
    given_name,
    family_name,
    address,
    salutation,
    address_on_first_name_terms,
    notes,
    primary_contact,
    add_groups,
    remove_groups,
    remove_emails,
    remove_phones,
    remove_postal_addresses,
    email_address_types,
    phone_number_types,
    postal_address_types,
    organization,
    is_archived,
    dry_run,
    ignore_warnings,
    as_json,
):
    """Change the names, the salutation, the notes, the primary contact, the
    organization and the groups of a person, remove email addresses, phone
    numbers and postal addresses, change their types or archive them, like in the web interface. Projects, deals and invoices keep their customer and contact
    when moving a person to another organization."""
    data = {
        key: value
        for key, value in [
            ("given_name", given_name),
            ("family_name", family_name),
            ("address", address),
            ("salutation", salutation),
            ("address_on_first_name_terms", address_on_first_name_terms),
            ("notes", notes),
            ("primary_contact", primary_contact),
            ("add_groups", list(add_groups)),
            ("remove_groups", list(remove_groups)),
            ("remove_email_addresses", list(remove_emails)),
            ("remove_phone_numbers", list(remove_phones)),
            ("remove_postal_addresses", list(remove_postal_addresses)),
            ("email_address_types", dict(email_address_types)),
            ("phone_number_types", dict(phone_number_types)),
            ("postal_address_types", dict(postal_address_types)),
            ("is_archived", is_archived),
        ]
        if value not in (None, [], {})
    }
    if organization is not None:
        if organization.strip() and not organization.strip().isdigit():
            terminate(f"--organization must be an ID or empty, not {organization!r}.")
        data["organization"] = int(organization) if organization.strip() else None
    if not data:
        terminate("Nothing to change, see --help for the options.")
    data = request(
        "PATCH",
        f"contacts/people/{person_id}/",
        json=data,
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing changed:")
    _echo_person(data)


@people.command("change-address")
@click.argument("person_id", type=int)
@click.option(
    "--address",
    "address_id",
    type=int,
    required=True,
    help="ID of the address from `wb people show`.",
)
@click.option("--type", "type_", help="E.g. Work or Home.")
@click.option("--street")
@click.option("--house-number")
@click.option("--address-suffix")
@click.option("--postal-code")
@click.option("--city")
@click.option("--country", help="ISO 3166-1 code, e.g. CH.")
@click.option(
    "--override",
    help="Replaces the whole address if set; an empty string removes it.",
)
@click.option("--dry-run", is_flag=True, help="Validate and show the result only.")
@click.option("--json", "as_json", is_flag=True)
def change_person_address(
    person_id,
    address_id,
    type_,
    street,
    house_number,
    address_suffix,
    postal_code,
    city,
    country,
    override,
    dry_run,
    as_json,
):
    """Change a postal address of a person; fields which aren't given stay.
    `wb organizations change-address` changes an address of several people
    at once."""
    data = {
        key: value
        for key, value in [
            ("type", type_),
            ("street", street),
            ("house_number", house_number),
            ("address_suffix", address_suffix),
            ("postal_code", postal_code),
            ("city", city),
            ("country", country),
            ("postal_address_override", override),
        ]
        if value is not None
    }
    if not data:
        terminate("Nothing to change, pass the fields of the new address.")
    data = request(
        "PATCH",
        f"contacts/people/{person_id}/postal-addresses/{address_id}/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing changed:")
    _echo_person(data)


@people.command("duplicates")
@page_options
@click.option("--json", "as_json", is_flag=True)
def people_duplicates(limit, offset, as_json):
    """Groups of possible duplicates: people with the same name, or with the
    same email address and a common given or family name

    The first person of a group is usually the one to keep (active, oldest),
    merge the others with `wb people merge ID --into ID`."""
    data = request(
        "GET", "contacts/people/duplicates/", params=page_params(limit, offset)
    )
    if as_json:
        echo_json(data)
        return
    table = make_table(
        "Group>", "ID>", "Name", "Organization", "Email addresses", "Primary contact"
    )
    for index, group in enumerate(data["items"], start=(offset or 0) + 1):
        for person in group["people"]:
            organization = person["organization"] or {}
            table.add_row(
                str(index),
                link(person["id"], person["url"]),
                link(person["full_name"], person["url"])
                + (" (archived)" if person["is_archived"] else ""),
                link(organization.get("name", ""), organization.get("url")),
                ", ".join(person["email_addresses"]),
                person["primary_contact"],
            )
        table.add_section()
    console.print(table)
    echo_more(data, offset, "groups")


def _echo_shared(rows, *, label, key, central_key, central_label):
    """Contact details of several people, or the organization's"""
    table = make_table(label, "Organization", "People")
    for row in rows:
        organization = row["organization"] or {}
        table.add_row(
            row[key] + (f" ({central_label})" if row[central_key] else ""),
            link(f"{organization['name']} ({organization['id']})", organization["url"])
            if organization
            else "",
            Text(", ").join(
                link(f"{person['full_name']} ({person['id']})", person["url"])
                for person in row["people"]
            ),
        )
    console.print(table)


@people.command("shared-emails")
@page_options
@click.option("--json", "as_json", is_flag=True)
def shared_emails(limit, offset, as_json):
    """Email addresses of several active people of the same organization, or
    the central address of their organization

    Usually generic addresses like info@: set them as the organization's
    address (`wb organizations update ID --email`) and remove them from the
    people (`wb people update ID --remove-email`)."""
    data = request(
        "GET",
        "contacts/people/shared-email-addresses/",
        params=page_params(limit, offset),
    )
    if as_json:
        echo_json(data)
        return
    _echo_shared(
        data["items"],
        label="Email address",
        key="email",
        central_key="is_organization_email",
        central_label="organization's address",
    )
    echo_more(data, offset, "email addresses")


@people.command("shared-phones")
@page_options
@click.option("--json", "as_json", is_flag=True)
def shared_phones(limit, offset, as_json):
    """Phone numbers of several active people of the same organization, or
    the central number of their organization

    Usually the reception: set it as the organization's number (`wb
    organizations update ID --phone-number`) and remove it from the people
    (`wb people update ID --remove-phone`)."""
    data = request(
        "GET",
        "contacts/people/shared-phone-numbers/",
        params=page_params(limit, offset),
    )
    if as_json:
        echo_json(data)
        return
    _echo_shared(
        data["items"],
        label="Phone number",
        key="phone_number",
        central_key="is_organization_phone_number",
        central_label="organization's number",
    )
    echo_more(data, offset, "phone numbers")


@people.command("reassign-suggestions")
@click.option(
    "--from",
    "primary_contact",
    help="Short name; defaults to everyone who isn't active anymore.",
    shell_complete=complete_short_names,
)
@click.option(
    "--since",
    type=click.DateTime(["%Y-%m-%d"]),
    help="Only projects and deals created since the date.",
)
@page_options
@click.option("--csv", "as_csv", is_flag=True, help="One row per result.")
@click.option("--json", "as_json", is_flag=True)
def reassign_suggestions(primary_contact, since, limit, offset, as_csv, as_json):
    """Suggest new primary contacts for people of users who left: the lead of
    the latest project or the owner of the latest deal, the person's own
    before those of their organization"""
    params = {}
    if primary_contact:
        params["primary_contact"] = primary_contact
    if since:
        params["since"] = since.date().isoformat()
    data = request(
        "GET", "contacts/people/reassign/", params=params | page_params(limit, offset)
    )
    if as_csv:
        echo_csv(data["items"])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
        "ID>", "Person", "Organization", "From", "Suggestion", "Source", "Date"
    )
    for row in data["items"]:
        person = row["person"]
        suggestion = row["suggestion"] or {}
        table.add_row(
            link(person["id"], person["url"]),
            person["full_name"],
            (person["organization"] or {}).get("name", ""),
            row["primary_contact"],
            suggestion.get("short_name", ""),
            link(
                f"{suggestion['source'].replace('_', ' ')}: {suggestion['title']}",
                suggestion["url"],
            )
            if suggestion
            else "",
            suggestion.get("created_at", "")[:10],
            style=None if suggestion else "dim",
        )
    console.print(table)
    echo_more(data, offset, "people")


@people.command("reassign")
@click.option(
    "--from",
    "former",
    help="Short name, also of someone who isn't active anymore. With"
    " --suggested it defaults to everyone who isn't active anymore.",
    shell_complete=complete_short_names,
)
@click.option(
    "--to", help="Short name of an active user.", shell_complete=complete_short_names
)
@click.option(
    "--suggested",
    is_flag=True,
    help="Reassign to the suggestions (see reassign-suggestions) instead.",
)
@click.option(
    "--since",
    type=click.DateTime(["%Y-%m-%d"]),
    help="With --suggested: only projects and deals created since the date.",
)
@click.option("--dry-run", is_flag=True, help="Validate and list the changes only.")
@click.option("--json", "as_json", is_flag=True)
def reassign_people(former, to, suggested, since, dry_run, as_json):
    """Reassign the active people of a user to another user or to the
    suggestions, e.g. when someone left"""
    if bool(to) == suggested:
        terminate("Pass either --to or --suggested.")
    if to and not former:
        terminate("--to needs --from.")
    data = request(
        "POST",
        "contacts/people/reassign/",
        json={
            "from": former,
            "to": to,
            "suggested": suggested,
            "since": since.date().isoformat() if since else None,
        },
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    table = make_table("ID>", "Person", "To")
    for change in data["changes"]:
        table.add_row(str(change["id"]), change["full_name"], change["to"])
    console.print(table)
    prefix = "Dry run, nothing changed: " if dry_run else ""
    console.print(
        f"{prefix}{len(data['changes'])} people reassigned"
        + (f" from {former}." if former else ".")
    )


@people.command("merge")
@click.argument("person_id", type=int)
@click.option("--into", type=int, required=True, help="ID of the person to keep.")
@click.option("--dry-run", is_flag=True, help="Validate and show the result only.")
@ignore_warnings_option
@click.option("--json", "as_json", is_flag=True)
def merge_person(person_id, into, dry_run, ignore_warnings, as_json):
    """Merge a duplicate into the person to keep and delete it

    Projects, deals, invoices, the linked user, contact details (except
    those the person to keep has already) and groups move, notes are
    appended. Name, organization and primary contact stay those of the
    person to keep."""
    data = request(
        "POST",
        f"contacts/people/{person_id}/merge/",
        json={"into": into},
        params={
            "dry_run": format_bool(dry_run),
            "ignore_warnings": list(ignore_warnings),
        },
    )
    if as_json:
        echo_json(data)
        return
    _echo_person(data)
    console.print(
        f"Dry run, nothing changed: {person_id} would be merged into {into}."
        if dry_run
        else f"{person_id} has been merged into {into}."
    )


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
@ignore_warnings_option
@click.option("--json", "as_json", is_flag=True)
def create_person(file, dry_run, allow_duplicates, ignore_warnings, as_json):
    """Create a person with their contact details from a YAML or JSON file

    Search for the person and their organization with `wb contacts search`
    first. Email addresses which are already in use are always rejected."""
    data = request(
        "POST",
        "contacts/people/",
        params={
            "dry_run": format_bool(dry_run),
            "allow_duplicates": format_bool(allow_duplicates),
            "ignore_warnings": list(ignore_warnings),
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
            ("Form of address", data["address"]),
            ("Salutation", data["salutation"]),
            (
                "First-name terms",
                "yes" if data["address_on_first_name_terms"] else "no",
            ),
            ("Primary contact", data["primary_contact"]),
            ("Groups", ", ".join(data["groups"])),
            *(
                (f"{label} ({detail['type']}, ID {detail['id']})", detail["value"])
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
@click.option("--include-archived", is_flag=True, help="Also archived groups.")
@page_options
@click.option("--json", "as_json", is_flag=True)
def search_groups(query, include_archived, limit, offset, as_json):
    """Search groups with their active people and organizations"""
    params = {"q": " ".join(query), "include_archived": format_bool(include_archived)}
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
            ("pinned", data["is_pinned"]),
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
@click.option(
    "--pin/--unpin", "is_pinned", default=None, help="Pinned groups are listed first."
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def update_group(
    group_id, title, is_archived, applies_to_organizations, is_pinned, dry_run, as_json
):
    """Rename, pin or archive a group"""
    data = {
        key: value
        for key, value in [
            ("title", title),
            ("is_archived", is_archived),
            ("applies_to_organizations", applies_to_organizations),
            ("is_pinned", is_pinned),
        ]
        if value is not None
    }
    if not data:
        terminate(
            "Nothing to change, pass --title, --archive, --unarchive,"
            " --applies-to-organizations, --applies-to-people, --pin or --unpin."
        )
    data = request(
        "PATCH",
        f"contacts/groups/{group_id}/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    echo_json(data) if as_json else _echo_group(data, dry_run=dry_run)
