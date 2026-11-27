"""Hosted sites"""

import click

from wb.core import (
    change_options,
    change_params,
    cli,
    complete_short_names,
    console,
    echo_csv,
    echo_deleted,
    echo_fields,
    echo_json,
    echo_more,
    format_bool,
    link,
    make_table,
    page_options,
    page_params,
    request,
    terminate,
)


ROLES = ["outage", "it"]


@cli.group(invoke_without_command=True)
@click.pass_context
def sites(ctx):
    """Hosted sites, their servers, contacts and recurring invoices, requires
    the hosting feature

    Without a command, lists the active sites with problems."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(search_sites, problems=True)


@sites.command("search")
@click.argument("query", nargs=-1)
@click.option("--server", help="ID or title of the server.")
@click.option("--customer", type=int, help="Organization ID.")
@click.option(
    "--problems",
    is_flag=True,
    help="Only active sites without running recurring invoice (and without"
    " reason) or without contact for outages.",
)
@click.option("--include-archived", is_flag=True, help="Also archived sites.")
@page_options
@click.option(
    "--csv", "as_csv", is_flag=True, help="One row per site, e.g. to compare."
)
@click.option("--json", "as_json", is_flag=True)
def search_sites(
    query, server, customer, problems, include_archived, limit, offset, as_csv, as_json
):
    """Search sites by title, domain, customer or server, active ones by
    default"""
    params = {
        "q": " ".join(query),
        "problems": format_bool(problems),
        "include_archived": format_bool(include_archived),
    }
    if server:
        params["server"] = server
    if customer:
        params["customer"] = customer
    data = request("GET", "hosting/sites/", params=params | page_params(limit, offset))
    if as_csv:
        echo_csv([
            {
                "id": site["id"],
                "title": site["title"],
                "host_names": " ".join(site["host_names"]),
                "server": site["server"]["title"],
                "customer": site["customer"]["name"],
                "owned_by": site["owned_by"],
                "problems": " ".join(site["problems"]),
                "is_archived": site["is_archived"],
            }
            for site in data["items"]
        ])
        echo_more(data, offset)
        return
    if as_json:
        echo_json(data)
        return
    table = make_table(
        "ID>", "Title", "Server", "Customer", "Outage contacts", "Problems"
    )
    for site in data["items"]:
        table.add_row(
            link(site["id"], site["url"]),
            link(site["title"], site["url"]),
            site["server"]["title"],
            link(site["customer"]["name"], site["customer"]["url"]),
            ", ".join(
                contact["full_name"]
                for contact in site["contacts"]
                if contact["role"] == "outage"
            ),
            ", ".join(site["problems_labels"]),
        )
    console.print(table)
    echo_more(data, offset, "sites")


def _echo_site(data):
    echo_fields(
        data["title"],
        [
            ("ID", data["id"]),
            ("Further domains", ", ".join(data["domains"])),
            ("Server", data["server"]["title"]),
            ("Customer", link(data["customer"]["name"], data["customer"]["url"])),
            ("Owned by", data["owned_by"]),
            ("Password manager", data["password_manager_url"]),
            ("Without recurring invoice", data["no_invoice_reason"]),
            ("Archived", "yes" if data["is_archived"] else ""),
            ("Problems", ", ".join(data["problems_labels"])),
            ("URL", data["url"]),
        ],
        url=data["url"],
    )
    if data["notes"]:
        console.print()
        console.print(data["notes"])
    if data["contacts"]:
        console.print()
        table = make_table(
            "Person ID>", "Person", "Role", "Organization", "Email", "Phone"
        )
        for contact in data["contacts"]:
            organization = contact["organization"]
            table.add_row(
                str(contact["id"]),
                link(contact["full_name"], contact["url"]),
                contact["role_label"],
                organization["name"] if organization else "",
                contact["email"],
                contact["phone_number"],
            )
        console.print(table)
    if data["recurring_invoices"]:
        console.print()
        table = make_table("Recurring invoice ID>", "Title", "Periodicity", "Ends on")
        for invoice in data["recurring_invoices"]:
            table.add_row(
                link(invoice["id"], invoice["url"]),
                link(invoice["title"], invoice["url"]),
                invoice["periodicity_label"],
                invoice["ends_on"] or "",
            )
        console.print(table)


@sites.command("show")
@click.argument("site")
@click.option("--json", "as_json", is_flag=True)
def show_site(site, as_json):
    """Show a site (ID or title) with its contacts and recurring invoices"""
    data = request("GET", f"hosting/sites/{site}/")
    echo_json(data) if as_json else _echo_site(data)


def _site_options(fn):
    for option in reversed([
        click.option(
            "--domain",
            "domains",
            multiple=True,
            help="Further host name; repeat it for several.",
        ),
        click.option("--server", help="ID or title of the server."),
        click.option("--customer", type=int, help="Organization ID."),
        click.option(
            "--owned-by",
            help="Short name of who knows the site best.",
            shell_complete=complete_short_names,
        ),
        click.option("--password-manager-url", help="Link to the credentials."),
        click.option(
            "--no-invoice-reason",
            help="Why there's no recurring invoice, e.g. a maintenance contract.",
        ),
        click.option("--notes"),
        click.option("--dry-run", is_flag=True, help="Validate only."),
        click.option("--json", "as_json", is_flag=True),
    ]):
        fn = option(fn)
    return fn


def _site_data(**fields):
    return {key: value for key, value in fields.items() if value is not None}


@sites.command("create")
@click.option("--title", required=True, help="The main domain.")
@_site_options
def create_site(
    title,
    domains,
    server,
    customer,
    owned_by,
    password_manager_url,
    no_invoice_reason,
    notes,
    dry_run,
    as_json,
):
    """Create a site; the owner defaults to you"""
    if not (server and customer):
        terminate("--server and --customer are required.")
    data = request(
        "POST",
        "hosting/sites/",
        json=_site_data(
            title=title,
            domains=list(domains),
            server=server,
            customer=customer,
            owned_by=owned_by,
            password_manager_url=password_manager_url,
            no_invoice_reason=no_invoice_reason,
            notes=notes,
        ),
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing created:")
    _echo_site(data)


@sites.command("update")
@click.argument("site")
@click.option("--title", help="The main domain.")
@_site_options
@click.option("--no-domains", is_flag=True, help="Remove the further domains.")
@click.option("--archived/--not-archived", "is_archived", default=None)
def update_site(
    site,
    title,
    domains,
    server,
    customer,
    owned_by,
    password_manager_url,
    no_invoice_reason,
    notes,
    dry_run,
    as_json,
    no_domains,
    is_archived,
):
    """Change a site (ID or title), only the given fields; --domain replaces
    the further domains"""
    data = _site_data(
        title=title,
        domains=[] if no_domains else (list(domains) or None),
        server=server,
        customer=customer,
        owned_by=owned_by,
        password_manager_url=password_manager_url,
        no_invoice_reason=no_invoice_reason,
        notes=notes,
        is_archived=is_archived,
    )
    if not data:
        terminate("Nothing to change.")
    data = request(
        "PATCH",
        f"hosting/sites/{site}/",
        json=data,
        params={"dry_run": format_bool(dry_run)},
    )
    if as_json:
        echo_json(data)
        return
    if dry_run:
        console.print("Dry run, nothing saved:")
    _echo_site(data)


@sites.command("delete")
@click.argument("site")
@change_options(warnings=False)
def delete_site(site, dry_run, as_json):
    """Delete a site (ID or title), e.g. one created by mistake

    Sites which don't run anymore are archived instead (`wb sites update
    SITE --archived`). Its contacts are deleted too, its recurring invoices
    only lose their site."""
    data = request("DELETE", f"hosting/sites/{site}/", params=change_params(dry_run))
    echo_deleted(data, _echo_site, what=data["title"], dry_run=dry_run, as_json=as_json)


@sites.group()
def contacts():
    """Add and remove the contacts of a site"""


@contacts.command("add")
@click.argument("site")
@click.argument("person", type=int)
@click.option(
    "--role",
    type=click.Choice(ROLES),
    default="outage",
    show_default=True,
    help="outage: outages and maintenance, it: IT matters like DNS records.",
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def add_contact(site, person, role, dry_run, as_json):
    """Add a person (ID) as a contact of the site (ID or title)"""
    data = request(
        "POST",
        f"hosting/sites/{site}/contacts/",
        json={"person": person, "role": role},
        params={"dry_run": format_bool(dry_run)},
    )
    echo_json(data) if as_json else _echo_site(data)


@contacts.command("remove")
@click.argument("site")
@click.argument("person", type=int)
@click.option(
    "--role", type=click.Choice(ROLES), help="Only this role, all of them otherwise."
)
@click.option("--dry-run", is_flag=True, help="Validate only.")
@click.option("--json", "as_json", is_flag=True)
def remove_contact(site, person, role, dry_run, as_json):
    """Remove a person (ID) from the contacts of the site (ID or title)"""
    data = request(
        "POST",
        f"hosting/sites/{site}/contacts/remove/",
        json={"person": person, "role": role},
        params={"dry_run": format_bool(dry_run)},
    )
    echo_json(data) if as_json else _echo_site(data)
