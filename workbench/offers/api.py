import datetime as dt
from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _, override
from ninja import Field, P, Query, Router, Schema
from ninja.errors import HttpError, ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.api_codes import by_id_or_code
from workbench.api_keys import KEYS, OfferStatus, key
from workbench.contacts.models import postal_address_choices
from workbench.offers.forms import OfferCopyForm, OfferForm
from workbench.offers.models import (
    Offer,
    OfferHeading,
    normalize_external_reference,
    place_heading,
    validate_external_reference,
)
from workbench.projects.api import (
    DealRef,
    ProjectOut,
    ProjectSummary,
    ServiceTypeOut,
    deal_refs,
    project_out,
    project_summary,
)
from workbench.projects.models import Project, Service
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
    filter_date_range,
    full_clean,
    object_pk,
    patch_with_form,
    user_by_short_name,
    validate_form,
)
from workbench.tools.pdf import offer_filename, pdf_response


# Same as in the web interface
router = Router(auth=user_auth(feature=FEATURES.CONTROLLING), tags=["offers"])


class ServiceIn(InputSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    service_type: str | None = Field(
        default=None,
        description="Title of a service type. Only a suggestion: Fills in the"
        " effort type and the hourly rate unless they are given explicitly.",
    )
    effort_type: str | None = Field(
        default=None,
        max_length=50,
        description="Type of the effort shown on the offer, e.g. Design.",
    )
    hours: Number | None = Field(
        default=None,
        ge=0,
        description="Estimated hours, require an effort type and an hourly rate.",
    )
    hourly_rate: Number | None = Field(
        default=None,
        ge=0,
        description="Leave this out to use the rate of the service type unless"
        " the specification explicitly asks for a different rate.",
    )
    cost: Number | None = Field(
        default=None,
        description="Fixed costs in addition to the hours, e.g. licenses or hosting.",
    )
    third_party_costs: Number | None = Field(
        default=None,
        ge=0,
        description="Total incl. tax for third-party services contained in the cost.",
    )
    is_optional: bool = Field(
        default=False,
        description="Optional services are offered but not part of the total.",
    )


class OfferHeadingIn(InputSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    before: int = Field(
        ge=0,
        description="Index of the service (in `services`, starting at 0) which"
        " the heading comes before; the number of services puts it after the"
        " last one. Headings with the same index keep their order.",
    )


class OfferIn(InputSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    postal_address: str | None = Field(
        default=None,
        description="Defaults to the first postal address of the project's"
        " contact or customer.",
    )
    services: list[ServiceIn] = Field(min_length=1)
    headings: list[OfferHeadingIn] = Field(
        default=[],
        description="Headings structure the services, e.g. by phase. They have"
        " no amounts.",
    )


class OfferCreateIn(OfferIn):
    status: Literal["in_preparation", "service_group"] = Field(
        default="in_preparation",
        description="Service groups collect services without being offered,"
        " they may be created without services.",
    )
    external_reference: str = Field(
        default="", description="URLs separated by whitespace (also newlines)."
    )
    services: list[ServiceIn] = []


def offer_import_schema(*, service_types):
    """JSON schema of an offer which only allows the given service types"""
    schema = OfferIn.model_json_schema()
    properties = schema["$defs"]["ServiceIn"]["properties"]
    properties["service_type"]["anyOf"][0]["enum"] = service_types
    return schema


class OfferServiceOut(Schema):
    id: int | None
    position: int
    title: str
    description: str
    service_type: str | None = Field(
        description="The service type with the same effort type and hourly rate,"
        " if there is one."
    )
    effort_type: str
    effort_hours: Decimal | None
    effort_rate: Decimal | None
    cost: Decimal | None
    third_party_costs: Decimal | None
    service_hours: Decimal
    service_cost: Decimal
    is_optional: bool


class OfferHeadingOut(Schema):
    id: int | None
    position: int = Field(
        description="Headings and services are shown ordered by their position."
    )
    title: str
    description: str


class OfferWarning(Schema):
    loc: list[str | int]
    msg: str


class OfferOut(Schema):
    id: int | None
    code: str | None
    url: str | None
    title: str
    description: str
    project: ProjectSummary
    owned_by: str = Field(description="Short name.")
    status: OfferStatus
    status_label: str
    created_at: dt.datetime
    offered_on: dt.date | None
    closed_on: dt.date | None = Field(description="Date of acceptance or decline.")
    valid_until: dt.date | None
    work_completed_on: dt.date | None
    external_reference: str = Field(description="URLs, one per line.")
    subtotal: Decimal
    discount: Decimal
    total_excl_tax: Decimal
    liable_to_vat: bool
    tax_rate: Decimal
    total: Decimal
    services: list[OfferServiceOut]
    headings: list[OfferHeadingOut]
    deals: list[DealRef] | None = Field(
        description="Deals the offer is linked to; null without the deals feature."
    )
    warnings: list[OfferWarning] = Field(
        default=[],
        description="Things to look at in the services which were just written,"
        " e.g. services without hours or a cost (allowed, like in the web"
        " interface).",
    )


class OfferContext(Schema):
    project: ProjectOut
    offers: list[OfferOut]
    service_types: list[ServiceTypeOut]
    import_schema: dict


def _service_type_titles(request):
    """Service types by effort type and hourly rate, cached per request"""
    if not hasattr(request, "_service_type_titles"):
        request._service_type_titles = {
            (st.title, st.hourly_rate): st.title for st in ServiceType.objects.all()
        }
    return request._service_type_titles


def offer_out(offer, services, request):
    titles = _service_type_titles(request)
    for service in services:
        service.service_type = titles.get((service.effort_type, service.effort_rate))
    return {
        "id": offer.pk,
        "code": offer.code if offer.pk else None,
        "url": request.build_absolute_uri(offer.get_absolute_url())
        if offer.pk
        else None,
        "title": offer.title,
        "description": offer.description,
        "project": project_summary(offer.project, request),
        "owned_by": offer.owned_by.get_short_name(),
        "status": key("offer_status", offer.status),
        "status_label": offer.get_status_display(),
        "created_at": offer.created_at,
        "offered_on": offer.offered_on,
        "closed_on": offer.closed_on,
        "valid_until": offer.valid_until,
        "work_completed_on": offer.work_completed_on,
        "external_reference": offer.external_reference,
        "subtotal": offer.subtotal,
        "discount": offer.discount,
        "total_excl_tax": offer.total_excl_tax,
        "liable_to_vat": offer.liable_to_vat,
        "tax_rate": offer.tax_rate,
        "total": offer.total,
        "services": services,
        "headings": list(offer.headings.all()) if offer.pk else [],
        "deals": deal_refs(offer.deals.all() if offer.pk else [], request),
    }


def _project_offers(project, request):
    return [
        offer_out(offer, list(offer.services.all()), request)
        for offer in project.offers.select_related(
            "project__customer", "owned_by"
        ).prefetch_related("services", "headings", "deals")
    ]


@router.get("/projects/{project_id}/offers/context/", response=OfferContext)
def offer_context(request, project_id: int):
    """Everything needed to write an offer, and the schema of the offer"""
    project = get_object_or_404(
        Project.objects.select_related("customer", "contact", "owned_by"), pk=project_id
    )
    service_types = list(ServiceType.objects.all())
    return {
        "project": project_out(project, request),
        "offers": _project_offers(project, request),
        "service_types": service_types,
        "import_schema": offer_import_schema(
            service_types=[st.title for st in service_types]
        ),
    }


OFFER_STATUSES = KEYS["offer_status"]


class OfferFilter(DateRangeFilter):
    q: SearchQuery = ""
    status: Literal[tuple(OFFER_STATUSES)] | None = Field(
        default=None, description="Offer status, see /api/choices/."
    )
    project: ProjectID = None
    customer: OrganizationID = None
    owned_by: ShortName = None
    external_reference: str | None = Field(
        default=None, description="Exact match of one of the references"
    )
    without_deal: bool = Field(
        default=False,
        description="Only offers which aren't linked to a deal; accepted ones"
        " count on their own in the accepted deals report.",
    )


@router.get("/offers/", response=list[OfferOut])
@paginate
def offer_list_search(request, filters: Query[OfferFilter]):
    """Search offers, newest first; the period filters the offer date"""
    offers = (
        Offer.objects
        .select_related("project__customer", "owned_by")
        .prefetch_related("services", "headings", "deals")
        .order_by("-pk")
    )
    if filters.project:
        offers = offers.filter(project=filters.project)
    if filters.customer:
        offers = offers.filter(project__customer=filters.customer)
    if filters.status:
        offers = offers.filter(status=OFFER_STATUSES[filters.status])
    if filters.owned_by:
        offers = offers.filter(
            owned_by=user_by_short_name(filters.owned_by, param="owned_by")
        )
    if url := filters.external_reference:
        offers = offers.filter(
            Q(external_reference=url)
            | Q(external_reference__startswith=f"{url}\n")
            | Q(external_reference__endswith=f"\n{url}")
            | Q(external_reference__contains=f"\n{url}\n")
        )
    if filters.without_deal:
        offers = offers.filter(deals__isnull=True)
    if filters.q:
        offers = offers.search(filters.q)
    offers = filter_date_range(offers, filters, "offered_on")
    return Serialized(
        offers, lambda offer: offer_out(offer, list(offer.services.all()), request)
    )


@router.get("/offers/{offer_id}/", response=OfferOut)
def offer_detail(request, offer_id: str):
    """An offer by its ID or code (2026-0042-o01)"""
    offer = by_id_or_code(
        Offer.objects.select_related("project__customer", "owned_by"), offer_id
    )
    return offer_out(offer, list(offer.services.all()), request)


@router.get("/offers/{offer_id}/pdf/")
def offer_pdf(
    request,
    offer_id: str,
    *,
    signature_line: Query[
        bool, P(description="Add a line for the customer's signature.")
    ] = False,
):
    """The offer (by ID or code) as PDF, like in the web interface, optionally
    with a signature line for the customer's agreement"""
    offer = by_id_or_code(Offer.objects.all(), offer_id)
    pdf, response = pdf_response(offer_filename(offer))
    try:
        pdf.init_letter()
        pdf.process_offer(offer)
        if signature_line:
            pdf.add_agreement(offer)
        pdf.generate()
    except Exception as exc:
        raise HttpError(422, _("Unable to generate the PDF: {}").format(exc)) from exc
    return response


def _decimal(value, exp):
    return None if value is None else Decimal(str(value)).quantize(Decimal(exp))


# Model fields and their names in the API
SERVICE_FIELDS = {"effort_hours": "hours", "effort_rate": "hourly_rate"}


def _apply_service(service, values, *, service_types, loc, errors, warnings):
    """Apply ``values`` (fields of a ``ServiceIn``) to the service

    Creating, replacing, adding and updating services all use these rules.
    ``None`` clears a value, fields which aren't in ``values`` are left
    alone. Service types fill in the effort type and the hourly rate unless
    those are given too, the project's flat rate always wins."""
    for field in ["title", "description"]:
        if field in values:
            setattr(service, field, values[field] or "")
    if "is_optional" in values:
        service.is_optional = bool(values["is_optional"])
    for field, model_field, exp in [
        ("hours", "effort_hours", "0.0"),
        ("cost", "cost", "0.00"),
        ("third_party_costs", "third_party_costs", "0.00"),
    ]:
        if field in values:
            setattr(service, model_field, _decimal(values[field], exp))

    # The logbook of invoiced work would be valued differently
    invoiced = service.is_invoiced
    effort = (service.effort_type, service.effort_rate)
    unknown_service_type = False
    if (title := values.get("service_type")) is not None:
        if service_type := service_types.get(title):
            service.effort_type = service_type.title
            service.effort_rate = service_type.hourly_rate
        else:
            unknown_service_type = True
            errors.append({
                "loc": [*loc, "service_type"],
                "msg": _("Unknown service type %r.") % title,
            })
    if "effort_type" in values:
        service.effort_type = values["effort_type"] or ""
    if "hourly_rate" in values:
        service.effort_rate = _decimal(values["hourly_rate"], "0.00")
    if service.project.flat_rate is not None and not invoiced:
        with override(settings.WORKBENCH.PDF_LANGUAGE):
            service.effort_type = _("flat rate")
        service.effort_rate = service.project.flat_rate
    if invoiced and (service.effort_type, service.effort_rate) != effort:
        errors.append({
            "loc": [*loc, "hourly_rate"],
            "msg": _(
                "This service has been invoiced already,"
                " its effort type and rate cannot be changed."
            ),
        })

    if (
        service.effort_hours is not None
        and not service.effort_type
        and service.effort_rate is None
        and not unknown_service_type
    ):
        errors.append({
            "loc": [*loc, "hours"],
            "msg": _(
                "Hours require an effort type and an hourly rate,"
                " e.g. from a service type."
            ),
        })
    # Allowed like in the web interface, e.g. for offers which several
    # people estimate one service after the other
    if service.effort_hours is None and service.cost is None:
        warnings.append({
            "loc": [*loc],
            "msg": _("%s: Neither hours nor a cost have been given yet.")
            % service.title,
        })

    service_errors = []
    full_clean(service, loc, service_errors, exclude=["project", "offer"])
    for error in service_errors:
        error["loc"][-1] = SERVICE_FIELDS.get(error["loc"][-1], error["loc"][-1])
    errors.extend(service_errors)


def _service_types():
    return {st.title: st for st in ServiceType.objects.all()}


def _build_services(project, data, errors, warnings):
    service_types = _service_types()
    services = []
    for index, item in enumerate(data.services):
        service = Service(project=project, position=10 * (index + 1))
        _apply_service(
            service,
            item.model_dump(exclude_none=True),
            service_types=service_types,
            loc=["body", "data", "services", index],
            errors=errors,
            warnings=warnings,
        )
        services.append(service)
    return services


def _build_headings(data, errors):
    """Headings and the index of the service they come before"""
    headings = []
    for index, item in enumerate(data.headings):
        if item.before > len(data.services):
            errors.append({
                "loc": ["body", "data", "headings", index, "before"],
                "msg": _("There are only %s services.") % len(data.services),
            })
        heading = OfferHeading(title=item.title, description=item.description)
        full_clean(
            heading,
            ["body", "data", "headings", index],
            errors,
            exclude=["offer", "position"],
        )
        headings.append((item.before, heading))
    return headings


def _arrange(services, headings):
    """Positions for the services and the headings in front of them"""
    items = []
    for index, service in enumerate(services):
        items.extend(heading for before, heading in headings if before == index)
        items.append(service)
    items.extend(heading for before, heading in headings if before >= len(services))
    for index, item in enumerate(items, 1):
        item.position = 10 * index


def _save(offer, services, request, *, dry_run, delete=(), headings=None, warnings=()):
    """Save everything and return the offer, roll back with ``dry_run``

    ``headings`` (pairs of the index of the service they come before and the
    heading) replace the offer's headings unless they are ``None``. Objects
    which only exist because of the dry run have no ID and URL."""
    existing = set(offer.services.values_list("id", flat=True)) if offer.pk else set()
    is_new = offer.pk is None
    if headings is not None:
        _arrange(services, headings)
    with transaction.atomic():
        for service in delete:
            service.delete()
        offer.save()
        for service in services:
            service.offer = offer
            service.save(skip_related_model=True)
        if headings is not None:
            offer.headings.all().delete()
            for _before, heading in headings:
                heading.offer = offer
                heading.save()
        offer.save()  # Recalculate the total
        result = offer_out(offer, list(offer.services.all()), request)
        result["warnings"] = list(warnings)
        if dry_run:
            transaction.set_rollback(True)
            if is_new:
                result |= {"id": None, "code": None, "url": None}
            for service in result["services"]:
                if service.id not in existing:
                    service.id = None
            if headings is not None:
                for heading in result["headings"]:
                    heading.id = None
    return result


@router.post("/projects/{project_id}/offers/", response=OfferOut)
def offer_create(
    request, project_id: int, data: OfferCreateIn, *, dry_run: DryRun = False
):
    """Create an offer in preparation or a service group with its services

    Nothing is saved if anything is invalid or with ``dry_run``."""
    project = get_object_or_404(
        Project.objects.select_related("customer", "contact"), pk=project_id
    )
    errors = []

    if project.closed_on:
        errors.append({
            "loc": ["path", "project_id"],
            "msg": _("The project is closed."),
        })
    if data.status == "in_preparation" and not data.services:
        errors.append({
            "loc": ["body", "data", "services"],
            "msg": _("Offers in preparation need at least one service."),
        })

    postal_address = data.postal_address
    if postal_address is None and (
        choices := postal_address_choices(
            person=project.contact, organization=project.customer
        )
    ):
        postal_address = choices[0][1]

    offer = Offer(
        project=project,
        title=data.title,
        description=data.description,
        owned_by=request.user,
        postal_address=postal_address or "",
        status=OFFER_STATUSES[data.status],
        external_reference=data.external_reference,
    )
    full_clean(offer, ["body", "data"], errors, exclude=["project", "_code"])
    warnings = []
    services = _build_services(project, data, errors, warnings)
    headings = _build_headings(data, errors)

    if errors:
        raise ValidationError(errors)

    return _save(
        offer,
        services,
        request,
        dry_run=dry_run,
        headings=headings,
        warnings=warnings,
    )


def _offer_in_preparation(offer_id, message):
    offer = get_object_or_404(
        Offer.objects.select_related(
            "project__customer", "project__contact", "owned_by"
        ),
        pk=offer_id,
    )
    if offer.status != Offer.IN_PREPARATION:
        raise HttpError(409, message)
    return offer


def _has_logbook(service):
    return service.loggedhours.exists() or service.loggedcosts.exists()


@router.put("/offers/{offer_id}/", response=OfferOut)
def offer_replace(request, offer_id: int, data: OfferIn, *, dry_run: DryRun = False):
    """Replace an offer in preparation and all its services

    Nothing is saved if anything is invalid or with ``dry_run``."""
    offer = _offer_in_preparation(
        offer_id, _("Only offers in preparation can be replaced.")
    )

    errors = []
    existing = list(offer.services.all())
    if any(_has_logbook(service) for service in existing):
        errors.append({
            "loc": ["path", "offer_id"],
            "msg": _(
                "Services of this offer already have logged hours or costs,"
                " they cannot be replaced."
            ),
        })
    if any(service.is_invoiced for service in existing):
        errors.append({
            "loc": ["path", "offer_id"],
            "msg": _(
                "Services of this offer have been invoiced already,"
                " they cannot be replaced."
            ),
        })

    offer.title = data.title
    offer.description = data.description
    if data.postal_address is not None:
        offer.postal_address = data.postal_address
    full_clean(offer, ["body", "data"], errors, exclude=["project", "_code"])
    warnings = []
    services = _build_services(offer.project, data, errors, warnings)
    headings = _build_headings(data, errors)

    if errors:
        raise ValidationError(errors)

    return _save(
        offer,
        services,
        request,
        dry_run=dry_run,
        delete=existing,
        headings=headings,
        warnings=warnings,
    )


class OfferPatch(InputSchema):
    """Fields which aren't given are left alone, null empties a field"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    owned_by: str | None = Field(
        default=None, description="Short name of an active user."
    )
    status: OfferStatus | None = Field(
        default=None,
        description="Offers which have been sent or accepted are put back into"
        " preparation to revise them (ignore the warning"
        " status-change-but-already-closed of accepted offers).",
    )
    offered_on: dt.date | None = None
    valid_until: dt.date | None = None
    closed_on: dt.date | None = Field(
        default=None,
        description="Date of acceptance or decline, defaults to today.",
    )
    work_completed_on: dt.date | None = Field(
        default=None, description="Stops logging on the offer's services."
    )
    postal_address: str | None = None
    discount: Number | None = Field(
        default=None, ge=0, description="Amount excl. tax, null removes it."
    )
    liable_to_vat: bool | None = None
    tax_rate: Number | None = Field(default=None, description="E.g. 8.1.")
    show_service_details: bool | None = None
    is_budget_retainer: bool | None = None
    external_reference: str | None = Field(
        default=None,
        description="URLs separated by whitespace; replaces the existing ones."
        " Changing only the external reference never warns.",
    )
    delete_planned_work: bool | None = Field(
        default=None,
        description="Required when declining or discarding an offer with"
        " planned work after this week: delete it or keep it.",
    )


@router.patch("/offers/{offer_id}/", response=OfferOut)
def offer_update(
    request,
    offer_id: int,
    data: OfferPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change an offer in any status, validated like in the web interface;
    its services and headings stay as they are

    Warnings of the web interface are errors here unless ignored by their
    code; nothing is saved if anything is invalid or with ``dry_run``."""
    patch = data.model_dump(exclude_unset=True)
    if patch.keys() == {"external_reference"}:
        return _update_external_reference(
            request, offer_id, patch["external_reference"], dry_run=dry_run
        )
    offer = get_object_or_404(
        Offer.objects.select_related(
            "project__customer", "project__contact", "owned_by"
        ),
        pk=offer_id,
    )
    if "discount" in patch and patch["discount"] is None:
        patch["discount"] = 0
    return patch_with_form(
        OfferForm,
        offer,
        patch,
        request,
        out=lambda offer: offer_out(offer, list(offer.services.all()), request),
        ignore_warnings=ignore_warnings,
        dry_run=dry_run,
        field_map={
            "owned_by": active_user,
            "status": api_key("offer_status"),
            "discount": lambda value: _decimal(value, "0.00"),
            "tax_rate": lambda value: _decimal(value, "0.00"),
            "delete_planned_work": int,
        },
        form_kwargs={"with_items": False},
    )


def _update_external_reference(request, offer_id, value, *, dry_run):
    """Only the external references, also of offers which have been sent or
    accepted (like in the web interface, which only warns)"""
    offer = get_object_or_404(
        Offer.objects.select_related(
            "project__customer", "project__contact", "owned_by"
        ),
        pk=offer_id,
    )
    try:
        validate_external_reference(value or "")
    except DjangoValidationError as exc:
        raise ValidationError([
            {"loc": ["body", "data", "external_reference"], "msg": message}
            for message in exc.messages
        ]) from None
    offer.external_reference = normalize_external_reference(value or "")
    with transaction.atomic():
        offer.save(update_fields=["external_reference"])
        result = offer_out(offer, list(offer.services.all()), request)
        if dry_run:
            transaction.set_rollback(True)
    return result


class OfferCopyIn(InputSchema):
    project: int | str = Field(description="ID or code of an open project.")


@router.post("/offers/{offer_id}/copy/", response=OfferOut)
def offer_copy(
    request,
    offer_id: str,
    data: OfferCopyIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Copy an offer (by ID or code) with its services and headings to a
    project, like in the web interface: the copy is in preparation and
    belongs to you

    Copying to the offer's own project is the warning same-project."""
    offer = by_id_or_code(Offer.objects.select_related("project"), offer_id)
    try:
        project = object_pk(Project.objects.all())(data.project)
    except DjangoValidationError as exc:
        raise ValidationError([
            {"loc": ["body", "data", "project"], "msg": message}
            for message in exc.messages
        ]) from None
    form = OfferCopyForm(
        {"project": project},
        project=offer.project,
        request=request,
        prefix=None,  # The web interface's is "modal"
    )
    validate_form(form, ignore_warnings=ignore_warnings)
    with transaction.atomic():
        new = offer.copy_to(project=form.cleaned_data["project"], owned_by=request.user)
        result = offer_out(new, list(new.services.all()), request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "code": None, "url": None}
            for item in [*result["services"], *result["headings"]]:
                item.id = None
    return result


# Headings of offers


class OfferHeadingCreateIn(InputSchema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    before: int | None = Field(
        default=None,
        description="ID of the offer's service which the heading comes before,"
        " leave this out to add it at the end.",
    )


class OfferHeadingPatch(InputSchema):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    before: int | None = Field(
        default=None,
        description="Moves the heading in front of this service of the offer"
        " (by ID), null moves it to the end.",
    )


def _heading_offer(offer):
    """Headings change with the services: only those of offers in
    preparation and of service groups"""
    if not offer.services_changeable:
        raise HttpError(
            409, _("Only the headings of offers in preparation can be changed.")
        )
    return offer


def _heading_before(offer, service_id):
    if service_id is None:
        return None
    if service := offer.services.filter(pk=service_id).first():
        return service
    raise ValidationError([
        {
            "loc": ["body", "data", "before"],
            "msg": _("The offer has no service with this ID."),
        }
    ])


def _heading_result(offer, request, *, dry_run, created=None):
    """The offer, rolled back with ``dry_run`` (new headings have no ID)"""
    result = offer_out(offer, list(offer.services.all()), request)
    if dry_run:
        transaction.set_rollback(True)
        for heading in result["headings"]:
            if created and heading.pk == created.pk:
                heading.id = None
    return result


@router.post("/offers/{offer_id}/headings/", response=OfferOut)
def offer_heading_create(
    request,
    offer_id: str,
    data: OfferHeadingCreateIn,
    *,
    dry_run: DryRun = False,
):
    """Add a heading to an offer (by ID or code) in preparation or a service
    group, in front of one of its services or at the end"""
    offer = _heading_offer(
        by_id_or_code(
            Offer.objects.select_related("project__customer", "owned_by"), offer_id
        )
    )
    before = _heading_before(offer, data.before)
    heading = OfferHeading(offer=offer, title=data.title, description=data.description)
    errors = []
    full_clean(heading, ["body", "data"], errors, exclude=["offer", "position"])
    if errors:
        raise ValidationError(errors)
    with transaction.atomic():
        place_heading(heading, before=before)
        return _heading_result(offer, request, dry_run=dry_run, created=heading)


@router.patch("/offers/headings/{int:heading_id}/", response=OfferOut)
def offer_heading_update(
    request, heading_id: int, data: OfferHeadingPatch, *, dry_run: DryRun = False
):
    """Change the title or the description of a heading or move it, only the
    given fields"""
    heading = get_object_or_404(
        OfferHeading.objects.select_related("offer__project", "offer__owned_by"),
        pk=heading_id,
    )
    offer = _heading_offer(heading.offer)
    fields = data.model_dump(exclude_unset=True)
    before = _heading_before(offer, fields.get("before"))
    for field in ["title", "description"]:
        if field in fields:
            setattr(heading, field, fields[field] or "")
    errors = []
    full_clean(heading, ["body", "data"], errors, exclude=["offer"])
    if errors:
        raise ValidationError(errors)
    with transaction.atomic():
        heading.save()
        if "before" in fields:
            place_heading(heading, before=before)
        return _heading_result(offer, request, dry_run=dry_run)


@router.delete("/offers/headings/{int:heading_id}/", response=OfferOut)
def offer_heading_delete(request, heading_id: int, *, dry_run: DryRun = False):
    """Delete a heading, the services stay where they are"""
    heading = get_object_or_404(
        OfferHeading.objects.select_related("offer__project", "offer__owned_by"),
        pk=heading_id,
    )
    offer = _heading_offer(heading.offer)
    with transaction.atomic():
        heading.delete()
        return _heading_result(offer, request, dry_run=dry_run)
