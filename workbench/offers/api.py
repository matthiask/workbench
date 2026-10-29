from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _, override
from ninja import Field, Router, Schema
from ninja.errors import HttpError, ValidationError

from workbench.accounts.api_auth import user_auth
from workbench.accounts.features import FEATURES
from workbench.contacts.models import postal_address_choices
from workbench.offers.models import Offer
from workbench.projects.api import ProjectOut, project_out
from workbench.projects.models import Project, Service
from workbench.services.models import ServiceType


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
    title: str
    description: str
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


def _offer_out(offer, services, request):
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
        _offer_out(offer, list(offer.services.all()), request)
        for offer in project.offers.select_related("project").prefetch_related(
            "services"
        )
    ]


@router.get("/projects/{project_id}/offers/", response=list[OfferOut])
def offer_list(request, project_id: int):
    """All offers of the project with their services"""
    return _project_offers(
        get_object_or_404(Project.objects.select_related("customer"), pk=project_id),
        request,
    )


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


@router.get("/offers/{offer_id}/", response=OfferOut)
def offer_detail(request, offer_id: int):
    offer = get_object_or_404(Offer.objects.select_related("project"), pk=offer_id)
    return _offer_out(offer, list(offer.services.all()), request)


def _decimal(value, exp):
    return None if value is None else Decimal(str(value)).quantize(Decimal(exp))


def _full_clean(instance, loc, errors, *, exclude=()):
    try:
        instance.full_clean(exclude=exclude)
    except DjangoValidationError as exc:
        errors.extend(
            {"loc": [*loc, field], "msg": message}
            for field, messages in exc.message_dict.items()
            for message in messages
        )


def _build_services(project, data, errors):
    service_types = {st.title: st for st in ServiceType.objects.all()}
    services = []
    for index, item in enumerate(data.services):
        loc = ["body", "data", "services", index]
        service = Service(
            project=project,
            title=item.title,
            description=item.description,
            effort_hours=_decimal(item.hours, "0.0"),
            cost=_decimal(item.cost, "0.00"),
            third_party_costs=_decimal(item.third_party_costs, "0.00"),
            is_optional=item.is_optional,
            position=10 * (index + 1),
        )

        if item.service_type is not None:
            if service_type := service_types.get(item.service_type):
                service.effort_type = service_type.title
                service.effort_rate = service_type.hourly_rate
            else:
                errors.append({
                    "loc": [*loc, "service_type"],
                    "msg": _("Unknown service type %r.") % item.service_type,
                })
        if item.effort_type is not None:
            service.effort_type = item.effort_type
        if item.hourly_rate is not None:
            service.effort_rate = _decimal(item.hourly_rate, "0.00")
        if project.flat_rate is not None:
            with override(settings.WORKBENCH.PDF_LANGUAGE):
                service.effort_type = _("flat rate")
            service.effort_rate = project.flat_rate

        if (
            item.hours is not None
            and not service.effort_type
            and service.effort_rate is None
            and (item.service_type is None or item.service_type in service_types)
        ):
            errors.append({
                "loc": [*loc, "hours"],
                "msg": _(
                    "Hours require an effort type and an hourly rate,"
                    " e.g. from a service type."
                ),
            })
        if item.hours is None and item.cost is None:
            errors.append({
                "loc": [*loc],
                "msg": _("Either hours or a cost are required."),
            })

        _full_clean(service, loc, errors, exclude=["project", "offer"])
        services.append(service)
    return services


def _save(offer, services, request, *, dry_run, delete=()):
    """Save everything and return the offer, roll back with ``dry_run``"""
    with transaction.atomic():
        for service in delete:
            service.delete()
        offer.save()
        for service in services:
            service.offer = offer
            service.save(skip_related_model=True)
        offer.save()  # Recalculate the total
        result = _offer_out(offer, list(offer.services.all()), request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
            for service in result["services"]:
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
    _full_clean(offer, ["body", "data"], errors, exclude=["project", "_code"])
    services = _build_services(project, data, errors)

    if errors:
        raise ValidationError(errors)

    return _save(offer, services, request, dry_run=dry_run)


@router.put("/offers/{offer_id}/", response=OfferOut)
def offer_replace(request, offer_id: int, data: OfferIn, *, dry_run: bool = False):
    """Replace an offer in preparation and all its services

    Nothing is saved if anything is invalid or with ``dry_run``."""
    offer = get_object_or_404(
        Offer.objects.select_related("project__customer", "project__contact"),
        pk=offer_id,
    )
    if offer.status != Offer.IN_PREPARATION:
        raise HttpError(409, _("Only offers in preparation can be replaced."))

    errors = []
    existing = list(offer.services.all())
    if any(
        service.loggedhours.exists() or service.loggedcosts.exists()
        for service in existing
    ):
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
    _full_clean(offer, ["body", "data"], errors, exclude=["project", "_code"])
    services = _build_services(offer.project, data, errors)

    if errors:
        raise ValidationError(errors)

    return _save(offer, services, request, dry_run=dry_run, delete=existing)
