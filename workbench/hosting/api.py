import datetime as dt
from typing import Literal

from django.db import transaction
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.contacts.api import (
    OrganizationOut,
    PersonSummary,
    organization_out,
    person_summary,
)
from workbench.contacts.models import Person
from workbench.hosting.forms import (
    ServerForm,
    ServerSearchForm,
    SiteContactForm,
    SiteForm,
    SiteSearchForm,
)
from workbench.hosting.models import Server, Site, SiteContact
from workbench.invoices.models import RecurringInvoice
from workbench.tools.api import (
    DryRun,
    InputSchema,
    OrganizationID,
    SearchQuery,
    Serialized,
    delete_with_form,
    form_data,
    raise_form_errors,
)


router = Router(auth=user_auth(feature=FEATURES.HOSTING), tags=["hosting"])

Role = Literal[tuple(key for key, _label in SiteContact.ROLE_CHOICES)]
Problem = Literal[tuple(Site.PROBLEMS)]


def _server(value, *, loc=None):
    """The server with this ID or title (case-insensitive)"""
    value = str(value).strip()
    servers = Server.objects.all()
    if server := (
        servers.filter(pk=int(value)).first()
        if value.isascii() and value.isdigit()
        else servers.filter(title__iexact=value).first()
    ):
        return server
    if loc:
        raise ValidationError([{"loc": loc, "msg": _("Unknown server %r.") % value}])
    raise Http404


def _site(value):
    """The site with this ID or title (case-insensitive)"""
    value = value.strip()
    sites = _sites()
    if value.isascii() and value.isdigit():
        return get_object_or_404(sites, pk=int(value))
    if site := sites.filter(title__iexact=value).first():
        return site
    raise Http404


def _sites():
    return (
        Site.objects
        .with_problem_flags()
        .select_related("server", "customer", "owned_by")
        .prefetch_related(
            Prefetch(
                "contacts",
                SiteContact.objects.select_related(
                    "person__organization"
                ).prefetch_related("person__emailaddresses", "person__phonenumbers"),
            ),
            Prefetch(
                "recurringinvoices",
                RecurringInvoice.objects.order_by("starts_on", "pk"),
            ),
        )
    )


# Servers


class ServerOut(Schema):
    id: int
    url: str
    title: str
    notes: str
    is_archived: bool


def _server_out(server, request):
    return {
        "id": server.id,
        "url": request.build_absolute_uri(server.get_absolute_url()),
        "title": server.title,
        "notes": server.notes,
        "is_archived": server.is_archived,
    }


class ServerFilter(Schema):
    include_archived: bool = Field(default=False, description="Also archived servers.")


@router.get("/hosting/servers/", response=list[ServerOut])
@paginate
def server_list(request, filters: Query[ServerFilter]):
    """Servers hosting sites, by title"""
    form = ServerSearchForm(
        {"s": "all" if filters.include_archived else ""}, request=request
    )
    form.is_valid()
    return Serialized(
        form.filter(Server.objects.all()).order_by("title", "pk"),
        lambda server: _server_out(server, request),
    )


class OutageContactOut(PersonSummary):
    organization: OrganizationOut | None
    email: str = Field(description="The first email address, empty if none.")
    phone_number: str = Field(description="The first phone number, empty if none.")
    sites: list[str] = Field(description="Titles of the person's sites on the server.")


class ServerDetailOut(ServerOut):
    sites: list[str] = Field(description="Titles of the active sites.")
    outage_contacts: list[OutageContactOut] = Field(
        description="Whom to inform about outages and maintenance: the active"
        " outage contacts of the active sites, each person once."
    )


def _first(related, attribute):
    return next((getattr(item, attribute) for item in related.all()), "")


@router.get("/hosting/servers/{server_id}/", response=ServerDetailOut)
def server_detail(request, server_id: str):
    """A server by ID or title, with the outage contacts of its active sites"""
    server = _server(server_id)
    return _server_out(server, request) | {
        "sites": [site.title for site in server.sites.active()],
        "outage_contacts": [
            person_summary(person, request)
            | {
                "organization": person.organization
                and organization_out(person.organization, request),
                "email": person.email,
                "phone_number": _first(person.phonenumbers, "phone_number"),
                "sites": [site.title for site in person.site_titles],
            }
            for person in server.outage_contacts()
        ],
    }


class ServerIn(InputSchema):
    title: str = Field(min_length=1, max_length=100)
    notes: str = ""


class ServerPatch(InputSchema):
    """Fields which aren't given are left alone"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    notes: str | None = None
    is_archived: bool | None = None


def _save_server(request, server, values, *, dry_run):
    # The form has a prefix (it's shown in modals)
    prefix = ServerForm(request=request).add_prefix
    form = ServerForm(
        {prefix(name): value for name, value in values.items()},
        instance=server,
        request=request,
    )
    if not form.is_valid(ignore_warnings=True):
        raise_form_errors(form)
    with transaction.atomic():
        result = _server_out(form.save(), request)
        if dry_run:
            transaction.set_rollback(True)
    return result


def _server_values(server, request):
    form = ServerForm(instance=server, request=request)
    return {name: form[name].value() for name in form.fields}


@router.post("/hosting/servers/", response=ServerOut)
def server_create(request, data: ServerIn, *, dry_run: DryRun = False):
    """Create a server"""
    server = Server()
    values = _server_values(server, request) | data.dict()
    return _save_server(request, server, values, dry_run=dry_run)


@router.patch("/hosting/servers/{server_id}/", response=ServerOut)
def server_update(
    request, server_id: str, data: ServerPatch, *, dry_run: DryRun = False
):
    """Rename or archive a server or change its notes"""
    server = _server(server_id)
    values = _server_values(server, request) | data.dict(exclude_unset=True)
    return _save_server(request, server, values, dry_run=dry_run)


@router.delete("/hosting/servers/{server_id}/", response=ServerOut)
def server_delete(request, server_id: str, *, dry_run: DryRun = False):
    """Delete a server (by ID or title) like in the web interface, e.g. one
    created by mistake; refused while it has sites, also archived ones
    (archive the server instead). Returns the deleted server."""
    server = _server(server_id)
    result = _server_out(server, request)
    delete_with_form(server, request, loc=["path", "server_id"], dry_run=dry_run)
    return result


# Sites


class SiteContactOut(PersonSummary):
    contact_id: int = Field(description="ID of the site contact.")
    role: Role
    role_label: str
    organization: OrganizationOut | None
    email: str = Field(description="The first email address, empty if none.")
    phone_number: str = Field(description="The first phone number, empty if none.")


class SiteRecurringInvoiceOut(Schema):
    id: int
    url: str
    title: str
    periodicity_label: str
    starts_on: dt.date
    ends_on: dt.date | None


class SiteServerOut(Schema):
    id: int
    title: str


class SiteOut(Schema):
    id: int
    url: str
    title: str
    domains: list[str]
    host_names: list[str] = Field(description="The title and the further domains.")
    server: SiteServerOut
    customer: OrganizationOut
    owned_by: str
    password_manager_url: str
    no_invoice_reason: str
    notes: str
    is_archived: bool
    problems: list[Problem]
    problems_labels: list[str]
    contacts: list[SiteContactOut]
    recurring_invoices: list[SiteRecurringInvoiceOut] | None = Field(
        description="Only with the controlling feature."
    )


def _site_out(site, request):
    controlling = request.user.features[FEATURES.CONTROLLING]
    problems = site.problem_keys()
    return {
        "id": site.id,
        "url": request.build_absolute_uri(site.get_absolute_url()),
        "title": site.title,
        "domains": site.domains.split(),
        "host_names": site.host_names(),
        "server": {"id": site.server.id, "title": site.server.title},
        "customer": organization_out(site.customer, request),
        "owned_by": site.owned_by.get_short_name(),
        "password_manager_url": site.password_manager_url,
        "no_invoice_reason": site.no_invoice_reason,
        "notes": site.notes,
        "is_archived": site.is_archived,
        "problems": problems,
        "problems_labels": [str(Site.PROBLEMS[key]) for key in problems],
        "contacts": [
            person_summary(contact.person, request)
            | {
                "contact_id": contact.id,
                "role": contact.role,
                "role_label": contact.get_role_display(),
                "organization": contact.person.organization
                and organization_out(contact.person.organization, request),
                "email": _first(contact.person.emailaddresses, "email"),
                "phone_number": _first(contact.person.phonenumbers, "phone_number"),
            }
            for contact in site.contacts.all()
        ],
        "recurring_invoices": [
            {
                "id": invoice.id,
                "url": request.build_absolute_uri(invoice.get_absolute_url()),
                "title": invoice.title,
                "periodicity_label": invoice.get_periodicity_display(),
                "starts_on": invoice.starts_on,
                "ends_on": invoice.ends_on,
            }
            for invoice in site.recurringinvoices.all()
        ]
        if controlling
        else None,
    }


class SiteFilter(Schema):
    q: SearchQuery = ""
    server: str | None = Field(default=None, description="ID or title of the server.")
    customer: OrganizationID = None
    problems: bool = Field(
        default=False, description="Only active sites with problems."
    )
    include_archived: bool = Field(default=False, description="Also archived sites.")


@router.get("/hosting/sites/", response=list[SiteOut])
@paginate
def site_list(request, filters: Query[SiteFilter]):
    """Sites by title, active ones by default, like the list in the web
    interface; the search finds titles, domains, customers and servers"""
    form = SiteSearchForm(
        {
            "q": filters.q,
            "s": "problems"
            if filters.problems
            else "all"
            if filters.include_archived
            else "",
        },
        request=request,
    )
    form.is_valid()
    sites = form.filter(_sites())
    if filters.server:
        sites = sites.filter(server=_server(filters.server, loc=["query", "server"]))
    if filters.customer:
        sites = sites.filter(customer=filters.customer)
    return Serialized(
        sites.order_by("title", "pk"), lambda site: _site_out(site, request)
    )


@router.get("/hosting/sites/{site_id}/", response=SiteOut)
def site_detail(request, site_id: str):
    """A site by ID or title"""
    return _site_out(_site(site_id), request)


class SiteIn(InputSchema):
    title: str = Field(min_length=1, max_length=200, description="The main domain.")
    domains: list[str] = Field(default=[], description="Further host names.")
    server: str = Field(description="ID or title of the server.")
    customer: int = Field(description="ID of the organization.")
    owned_by: str | None = Field(
        default=None,
        description="Short name of who knows the site best, defaults to the"
        " current user.",
    )
    password_manager_url: str = Field(
        default="", description="Link to the credentials, never the credentials."
    )
    no_invoice_reason: str = Field(
        default="", description="Why there's no recurring invoice, if there's none."
    )
    notes: str = ""


class SitePatch(InputSchema):
    """Fields which aren't given are left alone"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    domains: list[str] | None = Field(
        default=None, description="Further host names, replaces the existing ones."
    )
    server: str | None = Field(default=None, description="ID or title of the server.")
    customer: int | None = Field(default=None, description="ID of the organization.")
    owned_by: str | None = Field(default=None, description="Short name.")
    password_manager_url: str | None = None
    no_invoice_reason: str | None = None
    notes: str | None = None
    is_archived: bool | None = None


def _active_user(short_name, loc):
    from workbench.accounts.models import User

    if user := User.objects.by_short_name(short_name).filter(is_active=True).first():
        return user
    raise ValidationError([
        {"loc": loc, "msg": _("Unknown or inactive user %r.") % short_name}
    ])


def _save_site(request, site, data, *, dry_run):
    values = form_data(SiteForm(instance=site, request=request))
    for field, value in data.items():
        if field == "domains":
            values[field] = "\n".join(value)
        elif field == "server":
            values[field] = _server(value, loc=["body", "data", "server"]).pk
        elif field == "owned_by":
            values[field] = _active_user(value, ["body", "data", "owned_by"]).pk
        else:
            values[field] = "" if value is None else value
    form = SiteForm(values, instance=site, request=request)
    if not form.is_valid(ignore_warnings=True):
        raise_form_errors(form)
    with transaction.atomic():
        site = form.save()
        result = _site_out(_sites().get(pk=site.pk), request)
        if dry_run:
            transaction.set_rollback(True)
    return result


@router.post("/hosting/sites/", response=SiteOut)
def site_create(request, data: SiteIn, *, dry_run: DryRun = False):
    """Create a site, validated like in the web interface; the title and the
    domains are lowercased"""
    values = data.dict()
    if not values["owned_by"]:
        values["owned_by"] = request.user.get_short_name()
    return _save_site(request, Site(), values, dry_run=dry_run)


@router.patch("/hosting/sites/{site_id}/", response=SiteOut)
def site_update(request, site_id: str, data: SitePatch, *, dry_run: DryRun = False):
    """Change a site, e.g. move it to another server or archive it"""
    site = _site(site_id)
    return _save_site(request, site, data.dict(exclude_unset=True), dry_run=dry_run)


@router.delete("/hosting/sites/{site_id}/", response=SiteOut)
def site_delete(request, site_id: str, *, dry_run: DryRun = False):
    """Delete a site (by ID or title) like in the web interface, e.g. one
    created by mistake; sites which don't run anymore are archived instead

    Its contacts are deleted too, its recurring invoices stay and only lose
    their site (they're in the returned site, with the controlling
    feature). Returns the deleted site."""
    site = _site(site_id)
    result = _site_out(site, request)
    delete_with_form(site, request, loc=["path", "site_id"], dry_run=dry_run)
    return result


class SiteContactIn(InputSchema):
    person: int = Field(description="ID of the person.")
    role: Role = Field(description="outage (outages and maintenance) or it (DNS etc.).")


@router.post("/hosting/sites/{site_id}/contacts/", response=SiteOut)
def site_contact_add(
    request, site_id: str, data: SiteContactIn, *, dry_run: DryRun = False
):
    """Add a contact with a role to the site"""
    site = _site(site_id)
    prefix = SiteContactForm(site=site, request=request).add_prefix
    form = SiteContactForm(
        {prefix("person"): data.person, prefix("role"): data.role},
        site=site,
        request=request,
    )
    if not form.is_valid(ignore_warnings=True):
        raise_form_errors(form)
    with transaction.atomic():
        form.save()
        result = _site_out(_sites().get(pk=site.pk), request)
        if dry_run:
            transaction.set_rollback(True)
    return result


class SiteContactRemove(InputSchema):
    person: int = Field(description="ID of the person.")
    role: Role | None = Field(
        default=None, description="Only this role, all roles of the person otherwise."
    )


@router.post("/hosting/sites/{site_id}/contacts/remove/", response=SiteOut)
def site_contact_remove(
    request, site_id: str, data: SiteContactRemove, *, dry_run: DryRun = False
):
    """Remove a person (or one of their roles) from the site's contacts"""
    site = _site(site_id)
    contacts = site.contacts.filter(person=data.person)
    if data.role:
        contacts = contacts.filter(role=data.role)
    if not contacts.exists():
        person = Person.objects.filter(pk=data.person).first()
        raise ValidationError([
            {
                "loc": ["body", "data", "person"],
                "msg": _("%s isn't a contact of this site.") % (person or data.person),
            }
        ])
    with transaction.atomic():
        contacts.delete()
        result = _site_out(_sites().get(pk=site.pk), request)
        if dry_run:
            transaction.set_rollback(True)
    return result


def site_summary(site):
    return site and {"id": site.id, "title": site.title}
