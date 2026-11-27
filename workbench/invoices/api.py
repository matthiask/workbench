import copy
import datetime as dt
from decimal import Decimal
from typing import Literal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import F
from django.http import QueryDict
from django.shortcuts import get_object_or_404
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError, ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.api_codes import by_id_or_code
from workbench.api_keys import KEYS, InvoiceStatus, InvoiceType, Periodicity, key
from workbench.contacts.api import (
    OrganizationOut,
    PersonSummary,
    organization_out,
    person_summary,
)
from workbench.contacts.models import (
    Organization,
    Person,
    postal_address_choices,
)
from workbench.hosting.models import Site
from workbench.invoices.forms import (
    CreatePersonInvoiceForm,
    CreateProjectInvoiceForm,
    InvoiceDeleteForm,
    InvoiceForm,
    RecurringInvoiceForm,
    ServiceForm,
)
from workbench.invoices.models import (
    Invoice,
    ProjectedInvoice,
    RecurringInvoice,
    Service,
)
from workbench.offers.models import Offer
from workbench.projects.api import ProjectSummary, project_summary
from workbench.projects.models import Project
from workbench.services.models import ServiceType
from workbench.tools.api import (
    IGNORE_WARNINGS,
    DateRangeFilter,
    DryRun,
    InputSchema,
    Number,
    OrganizationID,
    ProjectID,
    SearchQuery,
    Serialized,
    ShortName,
    active_user,
    api_key,
    delete_with_form,
    filter_date_range,
    form_data,
    patch_with_form,
    user_by_short_name,
    validate_form,
    without_query,
)
from workbench.tools.formats import Z2, local_date_format
from workbench.tools.pdf import invoice_filename, pdf_response
from workbench.tools.validation import in_days


# Same as in the web interface
router = Router(auth=user_auth(feature=FEATURES.CONTROLLING), tags=["invoices"])

STATUSES = KEYS["invoice_status"]


class RecurringInvoiceSummary(Schema):
    id: int
    title: str
    url: str


class InvoiceOut(Schema):
    id: int
    code: str
    url: str
    title: str
    description: str
    type: InvoiceType
    type_label: str
    status: InvoiceStatus
    status_label: str
    project: ProjectSummary | None
    recurring_invoice: RecurringInvoiceSummary | None
    customer: OrganizationOut
    owned_by: str
    invoiced_on: dt.date | None
    due_on: dt.date | None
    closed_on: dt.date | None
    service_period_from: dt.date | None
    service_period_until: dt.date | None
    total_excl_tax: Decimal
    total: Decimal
    third_party_costs: Decimal | None
    postpone_reminders_until: dt.date | None


def invoice_out(invoice, request):
    return {
        "id": invoice.id,
        "code": invoice.code,
        "url": request.build_absolute_uri(invoice.get_absolute_url()),
        "title": invoice.title,
        "description": invoice.description,
        "type": invoice.type,
        "type_label": invoice.get_type_display(),
        "status": key("invoice_status", invoice.status),
        "status_label": invoice.get_status_display(),
        "project": project_summary(invoice.project, request)
        if invoice.project
        else None,
        "recurring_invoice": {
            "id": recurring.id,
            "title": recurring.title,
            "url": request.build_absolute_uri(recurring.get_absolute_url()),
        }
        if (recurring := invoice.recurring_invoice)
        else None,
        "customer": organization_out(invoice.customer, request),
        "owned_by": invoice.owned_by.get_short_name(),
        "invoiced_on": invoice.invoiced_on,
        "due_on": invoice.due_on,
        "closed_on": invoice.closed_on,
        "service_period_from": invoice.service_period_from,
        "service_period_until": invoice.service_period_until,
        "total_excl_tax": invoice.total_excl_tax,
        "total": invoice.total,
        "third_party_costs": invoice.third_party_costs,
        "postpone_reminders_until": invoice.postpone_reminders_until,
    }


class InvoiceServiceOut(Schema):
    id: int
    position: int
    title: str
    description: str
    effort_type: str
    effort_hours: Decimal | None
    effort_rate: Decimal | None
    cost: Decimal | None
    third_party_costs: Decimal | None
    service_hours: Decimal
    service_cost: Decimal
    project_service_id: int | None
    offer_id: int | None = Field(description="The offer of the project service")
    offer: str | None


class InvoiceDetailOut(InvoiceOut):
    services: list[InvoiceServiceOut] = Field(
        description="The lines of invoices for services, empty for fixed amount"
        " and down payment invoices."
    )


def _invoice_service_out(service):
    offer = service.project_service.offer if service.project_service else None
    return {
        "id": service.id,
        "position": service.position,
        "title": service.title,
        "description": service.description,
        "effort_type": service.effort_type,
        "effort_hours": service.effort_hours,
        "effort_rate": service.effort_rate,
        "cost": service.cost,
        "third_party_costs": service.third_party_costs,
        "service_hours": service.service_hours,
        "service_cost": service.service_cost,
        "project_service_id": service.project_service_id,
        "offer_id": offer.id if offer else None,
        "offer": offer.code if offer else None,
    }


def _invoice_services(invoice):
    if invoice.type in {Invoice.FIXED, Invoice.DOWN_PAYMENT}:
        return []
    return [
        _invoice_service_out(service)
        for service in invoice.services.select_related(
            "project_service__offer__project"
        ).order_by("position", "created_at", "pk")
    ]


class InvoiceFilter(DateRangeFilter):
    q: SearchQuery = ""
    project: ProjectID = None
    customer: OrganizationID = None
    owned_by: ShortName = None
    type: InvoiceType | None = Field(
        default=None, description="Invoice type, see /api/choices/."
    )
    status: InvoiceStatus | None = Field(
        default=None, description="Invoice status, see /api/choices/."
    )
    open: bool = Field(
        default=False, description="Only invoices which are in preparation or sent."
    )
    overdue: bool = Field(
        default=False, description="Only sent invoices past their due date."
    )


@router.get("/invoices/", response=list[InvoiceOut])
@paginate
def invoice_list(request, filters: Query[InvoiceFilter]):
    """Invoices, newest first; the period filters the invoice date

    ``open`` are invoices in preparation or sent, ``overdue`` invoices sent and
    due for more than 15 days (as for reminders)."""
    invoices = Invoice.objects.select_related(
        "project__customer", "recurring_invoice", "customer", "owned_by"
    )
    if filters.project:
        invoices = invoices.filter(project=filters.project)
    if filters.customer:
        invoices = invoices.filter(customer=filters.customer)
    if filters.owned_by:
        invoices = invoices.filter(
            owned_by=user_by_short_name(filters.owned_by, param="owned_by")
        )
    if filters.type:
        invoices = invoices.filter(type=filters.type)
    if filters.status:
        invoices = invoices.filter(status=STATUSES[filters.status])
    if filters.open:
        invoices = invoices.open()
    if filters.overdue:
        invoices = invoices.overdue()
    invoices = filter_date_range(invoices, filters, "invoiced_on")
    if filters.q:
        invoices = invoices.search(filters.q)
    return Serialized(
        invoices.order_by("-invoiced_on", "-pk"),
        lambda invoice: invoice_out(invoice, request),
    )


class ReminderInvoiceOut(InvoiceOut):
    last_reminded_on: dt.date | None
    days_overdue: int


class Reminders(Schema):
    customer: OrganizationOut
    contact: PersonSummary | None
    total_excl_tax: Decimal
    total: Decimal
    invoices: list[ReminderInvoiceOut]


def _overdue():
    return Invoice.objects.overdue().select_related(
        "customer", "contact__organization", "owned_by", "project__customer"
    )


# The web interface's reminders aren't restricted either
@router.get("/invoices/reminders/", response=list[Reminders], auth=user_auth())
def reminders(request):
    """Invoices overdue for more than 15 days whose reminders haven't been
    postponed, per customer and contact; contacts reminded longest ago
    first"""
    return _reminders(_overdue(), request)


def _reminders(invoices, request):
    invoices = invoices.order_by(
        F("last_reminded_on").asc(nulls_first=True), "invoiced_on"
    )
    today = dt.date.today()
    nested = {}
    for invoice in invoices:
        row = nested.setdefault(
            (invoice.customer, invoice.contact),
            {
                "customer": organization_out(invoice.customer, request),
                "contact": person_summary(invoice.contact, request)
                if invoice.contact
                else None,
                "total_excl_tax": Z2,
                "total": Z2,
                "invoices": [],
            },
        )
        row["total_excl_tax"] += invoice.total_excl_tax
        row["total"] += invoice.total
        row["invoices"].append(
            invoice_out(invoice, request)
            | {
                "last_reminded_on": invoice.last_reminded_on,
                "days_overdue": (today - invoice.due_on).days,
            }
        )
    return list(nested.values())


class PostponeReminders(InputSchema):
    until: dt.date | None = Field(
        description="No reminders before this date, null postpones nothing."
    )
    confirm: bool = Field(
        default=False,
        description="Confirms postponing by more than 30 days, which the web"
        " interface asks about too.",
    )


@router.post("/invoices/{invoice_id}/postpone-reminders/", response=InvoiceOut)
def postpone_reminders(request, invoice_id: int, data: PostponeReminders):
    """Leave a sent invoice out of the reminders until a date, e.g. while a
    question of the customer is being clarified"""
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            "project", "recurring_invoice", "customer", "owned_by"
        ),
        pk=invoice_id,
    )
    if invoice.status != Invoice.SENT:
        raise HttpError(409, _("Reminders can only be postponed for sent invoices."))
    loc = ["body", "data", "until"]
    if data.until and data.until > in_days(Invoice.MAX_POSTPONE_REMINDERS_DAYS):
        raise ValidationError([
            {
                "loc": loc,
                "msg": _(
                    "Reminders cannot be postponed by more than %(days)s days"
                    " (that would be later than %(date)s)."
                )
                % {
                    "days": Invoice.MAX_POSTPONE_REMINDERS_DAYS,
                    "date": local_date_format(
                        in_days(Invoice.MAX_POSTPONE_REMINDERS_DAYS)
                    ),
                },
            }
        ])
    if (
        data.until
        and data.until > in_days(Invoice.UNEXPECTED_POSTPONE_REMINDERS_DAYS)
        and not data.confirm
    ):
        raise ValidationError([
            {
                "loc": loc,
                "msg": _(
                    "You are postponing reminders until %(date)s, which is more"
                    " than %(days)s days from now. Are you sure?"
                )
                % {
                    "date": local_date_format(data.until),
                    "days": Invoice.UNEXPECTED_POSTPONE_REMINDERS_DAYS,
                },
            }
        ])
    invoice.postpone_reminders_until = data.until
    invoice.save(update_fields=["postpone_reminders_until"])
    return invoice_out(invoice, request)


TYPES = {
    "fixed": Invoice.FIXED,
    "down-payment": Invoice.DOWN_PAYMENT,
    "services": Invoice.SERVICES,
    "credit": Invoice.CREDIT,
}


class InvoiceIn(InputSchema):
    project: int | None = Field(
        default=None,
        description="Project ID; invoices without project are fixed amount"
        " invoices for a contact.",
    )
    offer: int | None = Field(
        default=None,
        description="Offer ID: a services invoice of the offer's project with"
        " the offer's title, description and services.",
    )
    contact: int | None = Field(
        default=None,
        description="Person ID, defaults to the project's contact. Required"
        " for invoices without project.",
    )
    type: Literal["fixed", "down-payment", "services", "credit"] | None = Field(
        default=None,
        description="Defaults to services with an offer or services, else fixed.",
    )
    services: list[int] | None = Field(
        default=None,
        description="Services invoices: IDs of the project's services to"
        " invoice, defaults to the offer's services with something to"
        " invoice. Required without offer.",
    )
    sources: dict[int, Literal["offer", "logbook"]] = Field(
        default_factory=dict,
        description="Services invoices: how single services (by ID) are"
        " invoiced: as offered or as logged (the hours and costs which haven't"
        " been invoiced yet; after invoicing the offer that's the surplus)."
        " Defaults to the offer for services with offered hours or costs which"
        " haven't been invoiced (nor declined), else to the logbook.",
    )
    disable_logging: list[int] = Field(
        default_factory=list,
        description="Services invoices: IDs of the services on which logging"
        " is disabled after invoicing them.",
    )
    logbook_cutoff_date: dt.date | None = Field(
        default=None,
        description="Services invoices from the logbook: only entries up to this date.",
    )
    title: str | None = Field(
        default=None,
        max_length=200,
        description="Defaults to the project's (and the offer's) title,"
        " required without project.",
    )
    description: str | None = Field(
        default=None,
        description="Defaults to the offer's or the project's description.",
    )
    subtotal: Decimal | None = Field(
        default=None,
        description="Required for fixed amount, down payment and credit"
        " invoices, calculated from the services otherwise.",
    )
    third_party_costs: Decimal = Field(
        default=Z2, description="Fixed amount and down payment invoices."
    )
    discount: Decimal | None = Field(
        default=None,
        description="Invoices of an offer default to its discount until an"
        " invoice of its services carries a discount, others to 0.",
    )
    liable_to_vat: bool = True
    tax_rate: Decimal | None = Field(
        default=None, description="Defaults to the current tax rate."
    )
    service_period_from: dt.date | None = None
    service_period_until: dt.date | None = None
    postal_address: str | None = Field(
        default=None,
        description="Defaults to the billing address of the contact, or else"
        " of the customer.",
    )
    owned_by: str | None = Field(
        default=None, description="Short name, defaults to you."
    )
    down_payments: list[int] = Field(
        default=[],
        description="IDs of the project's sent or paid down payment invoices"
        " to deduct (fixed amount and services invoices).",
    )


def _query(request, params):
    """The request with the query parameters of the web interface's invoice
    creation"""
    request = copy.copy(request)
    request.GET = QueryDict(mutable=True)
    request.GET.update(params)
    return request


def _invoice_form(request, data, error):  # noqa: C901
    """The bound invoice creation form of the web interface"""
    project = offer = None
    if data.offer is not None:
        offer = Offer.objects.select_related("project").filter(pk=data.offer).first()
        if not offer:
            error(["offer"], _("Unknown offer %r.") % data.offer)
            return None
        if data.project is not None and data.project != offer.project_id:
            error(["project"], _("The offer belongs to a different project."))
            return None
        project = offer.project
    elif data.project is not None:
        project = Project.objects.filter(pk=data.project).first()
        if not project:
            error(["project"], _("Unknown project %r.") % data.project)
            return None

    type = TYPES[
        data.type or ("services" if offer or data.services is not None else "fixed")
    ]
    if offer and type != Invoice.SERVICES:
        error(["type"], _("Invoices of an offer are services invoices."))
        return None
    if type != Invoice.SERVICES and data.subtotal is None:
        error(["subtotal"], _("This field is required."))

    if project:
        params = {"type": type}
        if type == Invoice.SERVICES and offer:
            params["offer"] = str(offer.pk)
        request = _query(request, params)

        def make_form(*args):
            return CreateProjectInvoiceForm(*args, project=project, request=request)

    else:
        if type != Invoice.FIXED:
            error(["type"], _("Invoices without project are fixed amount invoices."))
        if data.contact is None:
            error(["contact"], _("Invoices without project need a contact."))
            return None
        if not (contact := Person.objects.filter(pk=data.contact).first()):
            error(["contact"], _("Unknown person %r.") % data.contact)
            return None
        request = _query(request, {"contact": str(contact.pk)})

        def make_form(*args):
            return CreatePersonInvoiceForm(*args, request=request)

    form = make_form()
    values = form_data(form)
    for field in ["title", "description", "postal_address", "tax_rate"]:
        if (value := getattr(data, field)) is not None:
            values[field] = value
    for field in [
        "subtotal",
        "third_party_costs",
        "discount",
        "service_period_from",
        "service_period_until",
        "logbook_cutoff_date",
    ]:
        if (value := getattr(data, field)) is not None:
            # The form drops fields which don't apply to the type (e.g.
            # discounts of credits), don't ignore them silently
            if field not in form.fields:
                error([field], _("Not available for this type of invoice."))
            values[field] = value
    values["liable_to_vat"] = data.liable_to_vat or ""
    if data.contact is not None:
        values["contact"] = data.contact
    if data.owned_by is not None:
        if (
            user := User.objects
            .by_short_name(data.owned_by)
            .filter(is_active=True)
            .first()
        ):
            values["owned_by"] = user.pk
        else:
            error(["owned_by"], _("Unknown or inactive user %r.") % data.owned_by)
    if not values.get("postal_address"):
        contact = Person.objects.filter(pk=values.get("contact") or None).first()
        if choices := postal_address_choices(
            person=contact,
            organization=contact.organization if contact else project.customer,
            for_billing=True,
        ):
            values["postal_address"] = choices[0][1]
    if data.down_payments:
        if "apply_down_payment" in form.fields:
            values["apply_down_payment"] = data.down_payments
        else:
            error(["down_payments"], _("No down payments can be applied."))
    # Hours and costs of the lines come from their source (the web form
    # sends them, equal to the source's unless they have been changed)
    for name in values:
        if name.startswith(("effort_hours_", "cost_")):
            values[name] = ""
    # Per service fields exist for the services which may be invoiced, and
    # only apply to the services which are invoiced
    selected = set(
        data.services
        if data.services is not None
        else values.get("selected_services") or ()
    )
    not_selected = _("Service %s isn't one of the services to invoice.")
    for id, source in data.sources.items():
        if f"source_{id}" in form.fields and id in selected:
            values[f"source_{id}"] = source
        else:
            error(["sources", str(id)], not_selected % id)
    for index, id in enumerate(data.disable_logging):
        if f"disable_logging_{id}" in form.fields and id in selected:
            values[f"disable_logging_{id}"] = True
        else:
            error(["disable_logging", index], not_selected % id)
    if "selected_services" in form.fields:
        if data.services is not None:
            values["selected_services"] = data.services
        elif not offer:
            error(
                ["services"],
                _("Select the services to invoice, or invoice an offer."),
            )
    return make_form(values)


class InvoiceCreated(InvoiceDetailOut):
    id: int | None
    code: str | None
    url: str | None


@router.post("/invoices/", response=InvoiceCreated)
def invoice_create(
    request,
    data: InvoiceIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create an invoice in preparation (a draft), validated like in the web
    interface

    Warnings of the web interface are errors here unless ignored by their
    code; nothing is saved if anything is invalid or with ``dry_run``."""
    errors = []

    def error(loc, msg):
        errors.append({"loc": ["body", "data", *loc], "msg": msg})

    form = _invoice_form(request, data, error)
    if errors:
        raise ValidationError(errors)
    validate_form(
        form,
        fields={
            "selected_services": ["services"],
            "apply_down_payment": ["down_payments"],
        }
        | {
            field: ["sources", field.removeprefix("source_")]
            for field in form.fields
            if field.startswith("source_")
        },
        ignore_warnings=ignore_warnings,
    )

    with transaction.atomic():
        invoice = form.save()
        result = invoice_out(invoice, request) | {
            "services": _invoice_services(invoice)
        }
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "code": None, "url": None}
    return result


@router.get("/invoices/{invoice_id}/", response=InvoiceDetailOut)
def invoice_detail(request, invoice_id: str):
    """An invoice by its ID or code (2026-0042-0001, or 00042 without project)"""
    invoice = by_id_or_code(
        Invoice.objects.select_related(
            "project", "recurring_invoice", "customer", "owned_by"
        ),
        invoice_id,
    )
    return invoice_out(invoice, request) | {"services": _invoice_services(invoice)}


class InvoicePatch(InputSchema):
    """Fields which aren't given are left alone; the web interface's invoice
    form decides which fields an invoice can change (freezed invoices only a
    few, sent ones warn about changes)"""

    contact: int | None = Field(default=None, description="Person ID.")
    customer: int | None = Field(
        default=None,
        description="Organization ID, determined by the project for project invoices.",
    )
    invoiced_on: dt.date | None = None
    due_on: dt.date | None = None
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    service_period_from: dt.date | None = None
    service_period_until: dt.date | None = None
    owned_by: str | None = Field(default=None, description="Short name.")
    status: InvoiceStatus | None = Field(
        default=None,
        description="Only records the status, nothing is sent. Sent invoices"
        " can become paid or canceled.",
    )
    closed_on: dt.date | None = Field(
        default=None, description="Defaults to today for paid or canceled invoices."
    )
    payment_notice: str | None = None
    postal_address: str | None = None
    subtotal: Decimal | None = Field(
        default=None,
        description="Fixed amount, down payment and credit invoices (credits as"
        " a positive amount), calculated from the services otherwise.",
    )
    third_party_costs: Decimal | None = Field(
        default=None, description="Fixed amount and down payment invoices."
    )
    discount: Decimal | None = None
    liable_to_vat: bool | None = None
    tax_rate: Decimal | None = None
    show_service_details: bool | None = Field(
        default=None, description="Services invoices."
    )
    down_payments: list[int] | None = Field(
        default=None,
        description="IDs of the project's sent or paid down payment invoices"
        " to deduct (fixed amount and services invoices), replaces the"
        " current ones.",
    )


@router.patch("/invoices/{invoice_id}/", response=InvoiceOut)
def invoice_update(
    request,
    invoice_id: str,
    data: InvoicePatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change an invoice (by ID or code), validated like in the web interface,
    e.g. hand it over to another owner or settle it (status paid or canceled
    with closed_on and payment_notice)

    Setting the status to sent only records it, nothing is mailed. Warnings
    of the web interface are errors here unless ignored by their code;
    nothing is saved if anything is invalid or with ``dry_run``."""
    invoice = by_id_or_code(Invoice.objects.all(), invoice_id)
    return patch_with_form(
        InvoiceForm,
        invoice,
        data,
        request,
        out=lambda invoice: invoice_out(invoice, request),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map={
            "owned_by": active_user,
            "status": api_key("invoice_status"),
            "tax_rate": lambda value: Decimal(value).quantize(Z2),
            "down_payments": "apply_down_payment",
        },
    )


@router.delete("/invoices/{invoice_id}/", response=InvoiceOut)
def invoice_delete(
    request,
    invoice_id: str,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Delete an invoice in preparation (by ID or code) like in the web
    interface, e.g. one created twice; sent invoices are canceled instead

    The logged hours and costs and the down payments it deducted are
    released, which are warnings unless ignored by their code. Returns the
    deleted invoice."""
    invoice = by_id_or_code(Invoice.objects.all(), invoice_id)
    result = invoice_out(invoice, request)
    delete_with_form(
        invoice,
        request,
        loc=["path", "invoice_id"],
        delete_form_class=InvoiceDeleteForm,
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
    )
    return result


class InvoiceServiceFields(InputSchema):
    """Fields which aren't given are left alone, ``null`` clears values"""

    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, description="Null removes it.")
    service_type: str | None = Field(
        default=None,
        description="Title of a service type. Fills in the effort type and the"
        " hourly rate unless they are given too.",
    )
    effort_type: str | None = Field(default=None, max_length=50)
    effort_hours: Number | None = Field(default=None, description="Hours.")
    effort_rate: Number | None = Field(default=None, description="Hourly rate.")
    cost: Number | None = Field(
        default=None, description="Fixed costs in addition to hours."
    )
    third_party_costs: Number | None = Field(
        default=None,
        description="Total incl. tax for third parties contained in the cost.",
    )


class InvoiceServiceCreate(InvoiceServiceFields):
    title: str = Field(min_length=1, max_length=200)


class InvoiceServiceDetail(InvoiceServiceOut):
    invoice: InvoiceOut = Field(description="The invoice with its new total.")


class InvoiceServiceCreated(InvoiceServiceDetail):
    id: int | None
    position: int | None


class InvoiceServiceDeleted(InvoiceServiceDetail):
    warnings: list[str] = Field(
        description="Consequences to check by hand, e.g. a service period"
        " which doesn't match the remaining logged hours and costs anymore."
    )


def _invoice_service_patch(data):
    """The fields for ``patch_with_form()``, the service type fills in the
    effort type and the hourly rate like in the web interface"""
    patch = data.model_dump(exclude_unset=True)
    if (title := patch.pop("service_type", None)) is not None:
        if not (service_type := ServiceType.objects.filter(title=title).first()):
            raise ValidationError([
                {
                    "loc": ["body", "data", "service_type"],
                    "msg": _("Unknown service type %r.") % title,
                }
            ])
        patch.setdefault("effort_type", service_type.title)
        patch.setdefault("effort_rate", service_type.hourly_rate)
    return patch


def _invoice_service_detail(service, request):
    """The saved service and its invoice as stored (the invoice's total is
    recalculated when saving the service)"""
    service = Service.objects.select_related(
        "project_service__offer",
        "invoice__project__customer",
        "invoice__recurring_invoice",
        "invoice__customer",
        "invoice__owned_by",
    ).get(pk=service.pk)
    return _invoice_service_out(service) | {
        "invoice": invoice_out(service.invoice, request)
    }


@router.post("/invoices/{invoice_id}/services/", response=InvoiceServiceCreated)
def invoice_service_create(
    request,
    invoice_id: str,
    data: InvoiceServiceCreate,
    *,
    dry_run: DryRun = False,
):
    """Add a service to a services invoice in preparation (by ID or code),
    validated with the form of the web interface

    Returns the service and the invoice with its new total; the ID is null
    with ``dry_run``."""
    invoice = by_id_or_code(Invoice.objects.all(), invoice_id)
    if invoice.type != Invoice.SERVICES:
        raise ValidationError([
            {
                "loc": ["path", "invoice_id"],
                "msg": _("Only services invoices have services."),
            }
        ])
    result = patch_with_form(
        ServiceForm,
        Service(invoice=invoice),
        _invoice_service_patch(data),
        request,
        out=lambda service: _invoice_service_detail(service, request),
        dry_run=dry_run,
    )
    if dry_run:
        result |= {"id": None, "position": None}
    return result


@router.patch("/invoices/services/{int:service_id}/", response=InvoiceServiceDetail)
def invoice_service_update(
    request,
    service_id: int,
    data: InvoiceServiceFields,
    *,
    dry_run: DryRun = False,
):
    """Change a service of an invoice in preparation, validated with the
    form of the web interface

    Returns the service and the invoice with its new total."""
    service = get_object_or_404(
        Service.objects.select_related("invoice", "project_service__offer"),
        pk=service_id,
    )
    return patch_with_form(
        ServiceForm,
        service,
        _invoice_service_patch(data),
        request,
        out=lambda service: _invoice_service_detail(service, request),
        dry_run=dry_run,
    )


@router.delete("/invoices/services/{int:service_id}/", response=InvoiceServiceDeleted)
def invoice_service_delete(request, service_id: int, *, dry_run: DryRun = False):
    """Delete a service of an invoice in preparation like in the web
    interface; the hours and costs logged on it can be invoiced again

    Returns the deleted service, the invoice with its new total and the
    consequences to check by hand (``warnings``, the web interface shows
    them as messages)."""
    service = get_object_or_404(
        Service.objects.select_related("invoice", "project_service__offer"),
        pk=service_id,
    )
    result = _invoice_service_out(service)
    delete_with_form(service, request, loc=["path", "service_id"], dry_run=dry_run)
    return result | {
        "invoice": invoice_out(service.invoice, request),
        "warnings": [
            str(warning) for warning in getattr(service, "delete_warnings", ())
        ],
    }


@router.get("/invoices/{invoice_id}/pdf/")
def invoice_pdf(request, invoice_id: str):
    """The invoice (by ID or code) as PDF, like in the web interface"""
    invoice = by_id_or_code(Invoice.objects.all(), invoice_id)
    pdf, response = pdf_response(invoice_filename(invoice))
    try:
        pdf.init_invoice_letter()
        pdf.process_invoice(invoice)
        pdf.generate()
    except Exception as exc:
        raise HttpError(422, _("Unable to generate the PDF: {}").format(exc)) from exc
    return response


class ProjectedInvoiceOut(Schema):
    id: int
    project: ProjectSummary
    invoiced_on: dt.date
    gross_margin: Decimal
    description: str


def _projected_invoice_out(projected_invoice, request):
    return {
        "id": projected_invoice.id,
        "project": project_summary(projected_invoice.project, request),
        "invoiced_on": projected_invoice.invoiced_on,
        "gross_margin": projected_invoice.gross_margin,
        "description": projected_invoice.description,
    }


class ProjectedInvoiceFilter(DateRangeFilter):
    project: ProjectID = None
    customer: OrganizationID = None


@router.get(
    "/projected-invoices/",
    response=list[ProjectedInvoiceOut],
    auth=user_auth(feature=FEATURES.PROJECTED_GROSS_MARGIN),
)
@paginate
def projected_invoice_list_search(request, filters: Query[ProjectedInvoiceFilter]):
    """Planned invoicing (gross margin, third party costs are not included),
    oldest first; the period filters the planned invoice date"""
    projected = ProjectedInvoice.objects.select_related("project__customer")
    if filters.project:
        projected = projected.filter(project=filters.project)
    if filters.customer:
        projected = projected.filter(project__customer=filters.customer)
    projected = filter_date_range(projected, filters, "invoiced_on")
    return Serialized(
        projected.order_by("invoiced_on", "pk"),
        lambda row: _projected_invoice_out(row, request),
    )


NewInvoices = Literal[
    tuple(key for key, _label in RecurringInvoice.NEW_INVOICES_CHOICES)
]


class RecurringInvoiceSiteOut(Schema):
    id: int
    title: str


class RecurringInvoiceOut(Schema):
    id: int
    url: str
    title: str
    description: str
    customer: OrganizationOut
    contact: PersonSummary | None
    site: RecurringInvoiceSiteOut | None = Field(description="The hosted site.")
    owned_by: str
    periodicity: Periodicity
    periodicity_label: str
    postal_address: str
    starts_on: dt.date
    ends_on: dt.date | None
    create_invoice_on_day: int
    next_period_starts_on: dt.date | None
    subtotal: Decimal
    discount: Decimal
    liable_to_vat: bool
    total_excl_tax: Decimal
    total: Decimal
    third_party_costs: Decimal
    create_project: bool
    new_invoices: NewInvoices = Field(
        description="prepare, mark_as_sent or send (by email automatically)."
    )
    new_invoices_label: str
    send_to: str = Field(description="The recipient when sending by email.")
    mail_subject: str
    mail_body: str


def recurring_invoice_out(invoice, request):
    return {
        "id": invoice.id,
        "url": request.build_absolute_uri(invoice.get_absolute_url()),
        "title": invoice.title,
        "description": invoice.description,
        "customer": organization_out(invoice.customer, request),
        "contact": invoice.contact and person_summary(invoice.contact, request),
        "site": invoice.site and {"id": invoice.site.id, "title": invoice.site.title},
        "owned_by": invoice.owned_by.get_short_name(),
        "periodicity": invoice.periodicity,
        "periodicity_label": invoice.get_periodicity_display(),
        "postal_address": invoice.postal_address,
        "starts_on": invoice.starts_on,
        "ends_on": invoice.ends_on,
        "create_invoice_on_day": invoice.create_invoice_on_day,
        "next_period_starts_on": invoice.next_period_starts_on,
        "subtotal": invoice.subtotal,
        "discount": invoice.discount,
        "liable_to_vat": invoice.liable_to_vat,
        "total_excl_tax": invoice.total_excl_tax,
        "total": invoice.total,
        "third_party_costs": invoice.third_party_costs,
        "create_project": invoice.create_project,
        "new_invoices": invoice.new_invoices,
        "new_invoices_label": invoice.get_new_invoices_display(),
        "send_to": invoice.send_to,
        "mail_subject": invoice.mail_subject,
        "mail_body": invoice.mail_body,
    }


class RecurringInvoiceFilter(Schema):
    q: SearchQuery = ""
    customer: OrganizationID = None
    owned_by: ShortName = None
    new_invoices: NewInvoices | None = Field(
        default=None, description="Only those creating new invoices this way."
    )
    include_closed: bool = Field(
        default=False, description="Also those which don't renew anymore."
    )
    site: int | None = Field(default=None, description="ID of the hosted site.")


@router.get("/recurring-invoices/", response=list[RecurringInvoiceOut])
@paginate
def recurring_invoice_list(request, filters: Query[RecurringInvoiceFilter]):
    """Recurring invoices by customer, open ones by default (those whose
    auto-renewal hasn't been canceled before today)"""
    invoices = RecurringInvoice.objects.select_related(
        "customer", "contact", "owned_by", "site"
    )
    if not filters.include_closed:
        invoices = invoices.open()
    if filters.customer:
        invoices = invoices.filter(customer=filters.customer)
    if filters.owned_by:
        invoices = invoices.filter(
            owned_by=user_by_short_name(filters.owned_by, param="owned_by")
        )
    if filters.new_invoices:
        invoices = invoices.filter(new_invoices=filters.new_invoices)
    if filters.site:
        invoices = invoices.filter(site=filters.site)
    if filters.q:
        invoices = invoices.search(filters.q)
    return Serialized(
        invoices.order_by("customer__name", "title", "pk"),
        lambda invoice: recurring_invoice_out(invoice, request),
    )


@router.get("/recurring-invoices/{int:invoice_id}/", response=RecurringInvoiceOut)
def recurring_invoice_detail(request, invoice_id: int):
    return recurring_invoice_out(
        get_object_or_404(RecurringInvoice, pk=invoice_id), request
    )


class RecurringInvoicePatch(InputSchema):
    """Fields which aren't given are left alone; the web interface's form
    validates the result"""

    customer: int | None = Field(default=None, description="Organization ID.")
    contact: int | None = Field(
        default=None, description="Person ID (an employee of the customer)."
    )
    title: str | None = Field(
        default=None,
        max_length=200,
        description="Also the title of the invoices created.",
    )
    description: str | None = Field(
        default=None, description="Also the description of the invoices created."
    )
    owned_by: str | None = Field(
        default=None,
        description="Short name, also responsible for the invoices created.",
    )
    postal_address: str | None = None
    starts_on: dt.date | None = Field(
        default=None, description="Not on or before the freeze date."
    )
    ends_on: dt.date | None = Field(
        default=None,
        description="Cancel the auto-renewal on this date, null renews it"
        " again (creating the invoices of the periods in between warns).",
    )
    periodicity: Periodicity | None = None
    create_invoice_on_day: int | None = Field(
        default=None,
        description="Days relative to the start of the period, -20 creates"
        " invoices 20 days before their period begins.",
    )
    subtotal: Decimal | None = None
    third_party_costs: Decimal | None = None
    discount: Decimal | None = None
    liable_to_vat: bool | None = None
    create_project: bool | None = Field(
        default=None, description="Create a project for each invoice."
    )
    new_invoices: NewInvoices | None = Field(
        default=None,
        description="prepare, mark_as_sent or send (by email automatically).",
    )
    send_to: str | None = Field(
        default=None,
        description="The recipient when sending by email, proposed (like the"
        " subject and the text) when empty.",
    )
    mail_subject: str | None = None
    mail_body: str | None = Field(
        default=None,
        description="{code}, {total}, {due_on} and {service_period} are replaced"
        " with the values of each invoice.",
    )
    site: int | None = Field(
        default=None,
        description="ID of the hosted site (of the same customer), null"
        " removes it. Requires the hosting feature.",
    )


class RecurringInvoiceIn(RecurringInvoicePatch):
    """The customer, or a contact or a site giving it; the web interface's
    form validates the recurring invoice and proposes the rest"""


class RecurringInvoiceCreated(RecurringInvoiceOut):
    id: int | None
    url: str | None


def _recurring_invoice_request(request, data):
    """The request with the query parameter of the web interface's creation:
    the customer, else the contact or the site determining it"""
    for field, model in [
        ("customer", Organization),
        ("contact", Person),
        ("site", Site),
    ]:
        if (pk := data.get(field)) is not None and model.objects.filter(pk=pk).exists():
            return _query(request, {field: str(pk)})
    raise ValidationError([
        {
            "loc": ["body", "data", "customer"],
            "msg": _("This field is required.")
            if data.get("customer") is None
            else _("%(model)s %(value)r doesn't exist.")
            % {
                "model": capfirst(Organization._meta.verbose_name),
                "value": data["customer"],
            },
        }
    ])


@router.post("/recurring-invoices/", response=RecurringInvoiceCreated)
def recurring_invoice_create(
    request,
    data: RecurringInvoiceIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create a recurring invoice, validated like in the web interface

    The postal address defaults to the billing address of the contact or
    the customer, the responsible person to you, the start to today and
    third party costs to 0.
    Workbench creates (and sends, if wanted) the invoices itself. Warnings of
    the web interface are errors here unless ignored by their code; nothing
    is saved if anything is invalid or with ``dry_run``."""
    patch = data.model_dump(exclude_unset=True)
    request = _recurring_invoice_request(request, patch)
    values = form_data(form := RecurringInvoiceForm(request=request))
    errors = []
    for name, value in patch.items():
        field = form.fields.get(name)
        if not field or field.disabled:
            if value not in ("", None):
                errors.append({
                    "loc": ["body", "data", name],
                    "msg": _("This field cannot be changed."),
                })
            continue
        values[name] = "" if value is None else value
        if name == "owned_by" and value:
            try:
                values[name] = active_user(value)
            except DjangoValidationError as exc:
                errors.extend(
                    {"loc": ["body", "data", name], "msg": message}
                    for message in exc.messages
                )
    if errors:
        raise ValidationError(errors)
    if not values.get("postal_address"):
        contact = Person.objects.filter(pk=values.get("contact") or None).first()
        customer = Organization.objects.filter(
            pk=values.get("customer") or None
        ).first()
        if choices := postal_address_choices(
            person=contact, organization=customer, for_billing=True
        ):
            values["postal_address"] = choices[0][1]
    if "third_party_costs" not in patch:
        values["third_party_costs"] = Z2
    values[RecurringInvoiceForm.ignore_warnings_id] = " ".join(ignore_warnings)
    form = RecurringInvoiceForm(values, request=request)
    validate_form(form, ignore_warnings=ignore_warnings)

    with transaction.atomic():
        result = recurring_invoice_out(form.save(), request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
    return result


@router.patch("/recurring-invoices/{int:invoice_id}/", response=RecurringInvoiceOut)
def recurring_invoice_update(
    request,
    invoice_id: int,
    data: RecurringInvoicePatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change a recurring invoice, validated like in the web interface; the
    next period is computed and cannot be changed

    Warnings of the web interface are errors here unless ignored by their
    code; nothing is saved if anything is invalid or with ``dry_run``."""
    invoice = get_object_or_404(RecurringInvoice, pk=invoice_id)
    return patch_with_form(
        RecurringInvoiceForm,
        invoice,
        data,
        request,
        out=lambda invoice: recurring_invoice_out(invoice, request),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map={"owned_by": active_user},
        form_kwargs={"request": without_query(request)},
    )


@router.delete("/recurring-invoices/{int:invoice_id}/", response=RecurringInvoiceOut)
def recurring_invoice_delete(request, invoice_id: int, *, dry_run: DryRun = False):
    """Delete a recurring invoice like in the web interface, e.g. one created
    by mistake; the invoices it created stay. To stop creating invoices,
    cancel the auto-renewal (``ends_on``) instead. Returns the deleted
    recurring invoice."""
    invoice = get_object_or_404(RecurringInvoice, pk=invoice_id)
    result = recurring_invoice_out(invoice, request)
    delete_with_form(invoice, request, loc=["path", "invoice_id"], dry_run=dry_run)
    return result
