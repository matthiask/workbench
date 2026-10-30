from decimal import Decimal
from typing import Literal

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _, override
from ninja import Field, Query, Router, Schema
from ninja.errors import HttpError, ValidationError
from ninja.pagination import paginate

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.contacts.models import postal_address_choices
from workbench.offers.models import Offer
from workbench.projects.api import ProjectOut, project_out
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType
from workbench.tools.api import (
    DateRangeFilter,
    Serialized,
    filter_date_range,
    full_clean,
)


# Same as in the web interface
router = Router(auth=user_auth(feature=FEATURES.CONTROLLING), tags=["offers"])


class ServiceIn(Schema):
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
    hours: float | None = Field(
        default=None,
        ge=0,
        description="Estimated hours, require an effort type and an hourly rate.",
    )
    hourly_rate: float | None = Field(
        default=None,
        ge=0,
        description="Leave this out to use the rate of the service type unless"
        " the specification explicitly asks for a different rate.",
    )
    cost: float | None = Field(
        default=None,
        description="Fixed costs in addition to the hours, e.g. licenses or hosting.",
    )
    third_party_costs: float | None = Field(
        default=None,
        ge=0,
        description="Total incl. tax for third-party services contained in the cost.",
    )
    is_optional: bool = Field(
        default=False,
        description="Optional services are offered but not part of the total.",
    )


class OfferIn(Schema):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    postal_address: str | None = Field(
        default=None,
        description="Defaults to the first postal address of the project's"
        " contact or customer.",
    )
    services: list[ServiceIn] = Field(min_length=1)


def offer_import_schema(*, service_types):
    """JSON schema of an offer which only allows the given service types"""
    schema = OfferIn.model_json_schema()
    properties = schema["$defs"]["ServiceIn"]["properties"]
    properties["service_type"]["anyOf"][0]["enum"] = service_types
    return schema


class ServiceOut(Schema):
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


class OfferOut(Schema):
    id: int | None
    code: str | None
    url: str | None
    title: str
    description: str
    status: str
    subtotal: Decimal
    discount: Decimal
    total_excl_tax: Decimal
    liable_to_vat: bool
    tax_rate: Decimal
    total: Decimal
    services: list[ServiceOut]


class ServiceTypeOut(Schema):
    title: str
    hourly_rate: Decimal


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
        "status": offer.get_status_display(),
        "subtotal": offer.subtotal,
        "discount": offer.discount,
        "total_excl_tax": offer.total_excl_tax,
        "liable_to_vat": offer.liable_to_vat,
        "tax_rate": offer.tax_rate,
        "total": offer.total,
        "services": services,
    }


def _project_offers(project, request):
    return [
        offer_out(offer, list(offer.services.all()), request)
        for offer in project.offers.select_related("project").prefetch_related(
            "services"
        )
    ]


@router.get("/projects/{project_id}/offers/context/", response=OfferContext)
def offer_context(request, project_id: int):
    """Everything needed to write an offer, and the schema of the offer"""
    project = get_object_or_404(
        Project.objects.select_related("customer", "owned_by"), pk=project_id
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


OFFER_STATUSES = {
    "in_preparation": Offer.IN_PREPARATION,
    "service_group": Offer.SERVICE_GROUP,
    "offered": Offer.OFFERED,
    "accepted": Offer.ACCEPTED,
    "declined": Offer.DECLINED,
}


class OfferFilter(DateRangeFilter):
    q: str = ""
    status: (
        Literal["in_preparation", "service_group", "offered", "accepted", "declined"]
        | None
    ) = None
    project: int | None = None
    customer: int | None = None
    owned_by: str | None = None


@router.get("/offers/", response=list[OfferOut])
@paginate
def offer_list_search(request, filters: Query[OfferFilter]):
    """Search offers, newest first; the period filters the offer date"""
    offers = (
        Offer.objects
        .select_related("project")
        .prefetch_related("services")
        .order_by("-pk")
    )
    if filters.project:
        offers = offers.filter(project=filters.project)
    if filters.customer:
        offers = offers.filter(project__customer=filters.customer)
    if filters.status:
        offers = offers.filter(status=OFFER_STATUSES[filters.status])
    if filters.owned_by:
        offers = offers.filter(owned_by___short_name__iexact=filters.owned_by)
    if filters.q:
        offers = offers.search(filters.q)
    offers = filter_date_range(offers, filters, "offered_on")
    return Serialized(
        offers, lambda offer: offer_out(offer, list(offer.services.all()), request)
    )


@router.get("/offers/{offer_id}/", response=OfferOut)
def offer_detail(request, offer_id: int):
    offer = get_object_or_404(Offer.objects.select_related("project"), pk=offer_id)
    return offer_out(offer, list(offer.services.all()), request)


def _decimal(value, exp):
    return None if value is None else Decimal(str(value)).quantize(Decimal(exp))


# Model fields and their names in the API
SERVICE_FIELDS = {"effort_hours": "hours", "effort_rate": "hourly_rate"}


def _apply_service(service, values, *, service_types, loc, errors):
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
    if service.project.flat_rate is not None:
        with override(settings.WORKBENCH.PDF_LANGUAGE):
            service.effort_type = _("flat rate")
        service.effort_rate = service.project.flat_rate

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
    if service.effort_hours is None and service.cost is None:
        errors.append({
            "loc": [*loc],
            "msg": _("Either hours or a cost are required."),
        })

    service_errors = []
    full_clean(service, loc, service_errors, exclude=["project", "offer"])
    for error in service_errors:
        error["loc"][-1] = SERVICE_FIELDS.get(error["loc"][-1], error["loc"][-1])
    errors.extend(service_errors)


def _service_types():
    return {st.title: st for st in ServiceType.objects.all()}


def _build_services(project, data, errors):
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
        )
        services.append(service)
    return services


def _save(offer, services, request, *, dry_run, delete=()):
    """Save everything and return the offer, roll back with ``dry_run``

    Objects which only exist because of the dry run have no ID and URL."""
    existing = set(offer.services.values_list("id", flat=True)) if offer.pk else set()
    is_new = offer.pk is None
    with transaction.atomic():
        for service in delete:
            service.delete()
        offer.save()
        for service in services:
            service.offer = offer
            service.save(skip_related_model=True)
        offer.save()  # Recalculate the total
        result = offer_out(offer, list(offer.services.all()), request)
        if dry_run:
            transaction.set_rollback(True)
            if is_new:
                result |= {"id": None, "code": None, "url": None}
            for service in result["services"]:
                if service.id not in existing:
                    service.id = None
    return result


@router.post("/projects/{project_id}/offers/", response=OfferOut)
def offer_create(request, project_id: int, data: OfferIn, *, dry_run: bool = False):
    """Create an offer in preparation with its services

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
        status=Offer.IN_PREPARATION,
    )
    full_clean(offer, ["body", "data"], errors, exclude=["project", "_code"])
    services = _build_services(project, data, errors)

    if errors:
        raise ValidationError(errors)

    return _save(offer, services, request, dry_run=dry_run)


def _offer_in_preparation(offer_id, message):
    offer = get_object_or_404(
        Offer.objects.select_related("project__customer", "project__contact"),
        pk=offer_id,
    )
    if offer.status != Offer.IN_PREPARATION:
        raise HttpError(409, message)
    return offer


def _has_logbook(service):
    return service.loggedhours.exists() or service.loggedcosts.exists()


@router.put("/offers/{offer_id}/", response=OfferOut)
def offer_replace(request, offer_id: int, data: OfferIn, *, dry_run: bool = False):
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

    offer.title = data.title
    offer.description = data.description
    if data.postal_address is not None:
        offer.postal_address = data.postal_address
    full_clean(offer, ["body", "data"], errors, exclude=["project", "_code"])
    services = _build_services(offer.project, data, errors)

    if errors:
        raise ValidationError(errors)

    return _save(offer, services, request, dry_run=dry_run, delete=existing)


def _changeable_offer(offer_id):
    return _offer_in_preparation(
        offer_id, _("Only offers in preparation can be changed.")
    )


class OfferPatch(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    postal_address: str | None = None


@router.patch("/offers/{offer_id}/", response=OfferOut)
def offer_update(request, offer_id: int, data: OfferPatch, *, dry_run: bool = False):
    """Change the title, the description or the postal address of an offer
    in preparation; fields which aren't given are left alone"""
    offer = _changeable_offer(offer_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(offer, field, value or "")
    errors = []
    full_clean(offer, ["body", "data"], errors, exclude=["project", "_code"])
    if errors:
        raise ValidationError(errors)
    return _save(offer, [], request, dry_run=dry_run)


def _renumbered(services):
    for index, service in enumerate(services):
        service.position = 10 * (index + 1)
    return services


class ServiceAdd(ServiceIn):
    after: int | None = Field(
        default=None,
        description="ID of the service after which the new one is inserted,"
        " defaults to the end.",
    )


@router.post("/offers/{offer_id}/services/", response=OfferOut)
def offer_service_add(
    request, offer_id: int, data: ServiceAdd, *, dry_run: bool = False
):
    """Add a service to an offer in preparation, at the end or after another
    service"""
    offer = _changeable_offer(offer_id)
    services = list(offer.services.all())
    index = len(services)
    errors = []
    if data.after is not None:
        try:
            index = 1 + [service.id for service in services].index(data.after)
        except ValueError:
            errors.append({
                "loc": ["body", "data", "after"],
                "msg": _("The offer has no service with this ID."),
            })
    service = Service(project=offer.project)
    _apply_service(
        service,
        data.model_dump(exclude_none=True, exclude={"after"}),
        service_types=_service_types(),
        loc=["body", "data"],
        errors=errors,
    )
    if errors:
        raise ValidationError(errors)
    services.insert(index, service)
    return _save(offer, _renumbered(services), request, dry_run=dry_run)


class ServicePatch(Schema):
    """Fields which aren't given are left alone, ``null`` clears values"""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    service_type: str | None = Field(
        default=None,
        description="Title of a service type. Fills in the effort type and the"
        " hourly rate unless they are given too.",
    )
    effort_type: str | None = Field(default=None, max_length=50)
    hours: float | None = Field(default=None, ge=0)
    hourly_rate: float | None = Field(default=None, ge=0)
    cost: float | None = None
    third_party_costs: float | None = Field(default=None, ge=0)
    is_optional: bool | None = None


@router.patch("/offers/{offer_id}/services/{int:service_id}/", response=OfferOut)
def offer_service_update(
    request,
    offer_id: int,
    service_id: int,
    data: ServicePatch,
    *,
    dry_run: bool = False,
):
    """Change a service of an offer in preparation, also when hours or costs
    have already been logged on it (like in the web interface)"""
    offer = _changeable_offer(offer_id)
    service = get_object_or_404(offer.services.select_related("project"), pk=service_id)
    errors = []
    _apply_service(
        service,
        data.model_dump(exclude_unset=True),
        service_types=_service_types(),
        loc=["body", "data"],
        errors=errors,
    )
    if errors:
        raise ValidationError(errors)
    return _save(offer, [service], request, dry_run=dry_run)


@router.delete("/offers/{offer_id}/services/{int:service_id}/", response=OfferOut)
def offer_service_delete(
    request, offer_id: int, service_id: int, *, dry_run: bool = False
):
    """Delete a service of an offer in preparation, unless hours or costs have
    been logged on it; offers keep at least one service"""
    offer = _changeable_offer(offer_id)
    service = get_object_or_404(offer.services.all(), pk=service_id)
    errors = []
    if _has_logbook(service):
        errors.append({
            "loc": ["path", "service_id"],
            "msg": _(
                "Hours or costs have been logged on this service, it cannot be deleted."
            ),
        })
    if offer.services.count() == 1:
        errors.append({
            "loc": ["path", "service_id"],
            "msg": _("The last service of an offer cannot be deleted."),
        })
    if errors:
        raise ValidationError(errors)
    return _save(offer, [], request, dry_run=dry_run, delete=[service])


class ServiceOrder(Schema):
    services: list[int] = Field(
        description="The IDs of all services of the offer in the new order."
    )


@router.post("/offers/{offer_id}/services/reorder/", response=OfferOut)
def offer_service_reorder(
    request, offer_id: int, data: ServiceOrder, *, dry_run: bool = False
):
    """Reorder the services of an offer in preparation"""
    offer = _changeable_offer(offer_id)
    services = {service.id: service for service in offer.services.all()}
    if sorted(data.services) != sorted(services):
        raise ValidationError([
            {
                "loc": ["body", "data", "services"],
                "msg": _("Expected the IDs of all services of the offer once."),
            }
        ])
    return _save(
        offer,
        _renumbered([services[id] for id in data.services]),
        request,
        dry_run=dry_run,
    )
