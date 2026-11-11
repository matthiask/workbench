import datetime as dt
import itertools
from collections import defaultdict
from typing import Literal

from django.db import transaction
from django.db.models import Count, Prefetch, Q, TextField, Value
from django.db.models.functions import Concat, Lower, Trim
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, P, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.models import User
from workbench.contacts.forms import (
    GroupForm,
    GroupSearchForm,
    OrganizationMergeForm,
    OrganizationPostalAddressForm,
    PersonForm,
    PersonMergeForm,
    organization_update_warning,
    recent_projects_or_deals,
)
from workbench.contacts.merge import possible_duplicates
from workbench.contacts.models import (
    ADDRESS_FIELDS,
    EmailAddress,
    Group,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
    normalize_phone_number,
    organization_postal_addresses,
    unarchive_organization,
    update_organization_archival,
)
from workbench.contacts.reassign import primary_contact_suggestions
from workbench.tools.api import (
    IGNORE_WARNINGS,
    DryRun,
    InputSchema,
    OrganizationID,
    SearchQuery,
    Serialized,
    form_data,
    full_clean,
    raise_form_errors,
    validate_form,
)


router = Router(tags=["contacts"])


class OrganizationOut(Schema):
    id: int
    url: str
    name: str
    is_archived: bool


class PersonSummary(Schema):
    id: int
    url: str
    full_name: str
    is_archived: bool


class PersonOut(PersonSummary):
    given_name: str
    family_name: str
    organization: OrganizationOut | None


class PostalAddressOut(Schema):
    type: str
    street: str
    house_number: str
    address_suffix: str
    postal_code: str
    city: str
    country: str = Field(description="ISO 3166-1 code, e.g. CH")
    postal_address_override: str
    value: str = Field(description="The formatted address")


class PersonListOut(PersonOut):
    primary_contact: str
    groups: list[str] = Field(
        description="Active groups, also those of the organization which apply"
        " to organizations"
    )
    postal_address: PostalAddressOut | None = Field(
        description="The address with the highest weight, like the XLSX export"
        " of the people list"
    )


def _postal_address_out(person):
    if not (address := next(iter(person.postaladdresses.all()), None)):
        return None
    return {
        field: getattr(address, field)
        for field in [
            "type",
            "street",
            "house_number",
            "address_suffix",
            "postal_code",
            "city",
            "postal_address_override",
        ]
    } | {
        "country": address.country.code or "",
        "value": address.postal_address,
    }


def organization_out(organization, request):
    return {
        "id": organization.id,
        "url": request.build_absolute_uri(organization.get_absolute_url()),
        "name": organization.name,
        "is_archived": organization.is_archived,
    }


def person_summary(person, request):
    return {
        "id": person.id,
        "url": request.build_absolute_uri(person.get_absolute_url()),
        "full_name": person.full_name,
        "is_archived": person.is_archived,
    }


def person_list_out(person, request):
    return person_summary(person, request) | {
        "given_name": person.given_name,
        "family_name": person.family_name,
        "organization": organization_out(person.organization, request)
        if person.organization
        else None,
    }


class OrganizationFilter(Schema):
    q: SearchQuery = ""
    include_archived: bool = Field(default=False, description="Also archived contacts.")


class OrganizationSearchFilter(OrganizationFilter):
    without_active_people: bool = Field(
        default=False,
        description="Only organizations without active people, like the defined"
        " search of the web interface",
    )
    primary_contact: str | None = Field(default=None, description="Short name")
    several_postal_addresses: bool = Field(
        default=False,
        description="Only organizations whose active people have different postal"
        " addresses, e.g. old ones",
    )


@router.get("/contacts/organizations/", response=list[OrganizationOut])
@paginate
def organization_list(request, filters: Query[OrganizationSearchFilter]):
    """Search organizations, e.g. the customer of a new project"""
    organizations = Organization.objects.order_by("name", "pk")
    if not filters.include_archived:
        organizations = organizations.active()
    if filters.q:
        organizations = organizations.search(filters.q)
    if filters.without_active_people:
        organizations = organizations.exclude(people__is_archived=False)
    if filters.primary_contact:
        user = User.objects.by_short_name(filters.primary_contact).first()
        if not user:
            raise _query_error(
                "primary_contact", _("Unknown user %r.") % filters.primary_contact
            )
        organizations = organizations.filter(primary_contact=user)
    if filters.several_postal_addresses:
        address = Concat(
            *itertools.chain.from_iterable(
                (Lower(Trim(f"people__postaladdresses__{field}")), Value("|"))
                for field in ADDRESS_FIELDS
            ),
            output_field=TextField(),
        )
        organizations = organizations.annotate(
            addresses=Count(address, distinct=True, filter=Q(people__is_archived=False))
        ).filter(addresses__gt=1)
    return Serialized(
        organizations, lambda organization: organization_out(organization, request)
    )


class PersonFilter(OrganizationFilter):
    organization: OrganizationID = None
    group: str | None = Field(
        default=None,
        description="Title or ID of a group; also people who are in it through"
        " their organization",
    )
    without_groups: bool = Field(
        default=False, description="Only people in no active group"
    )
    missing_postal_address: bool = Field(
        default=False,
        description="Only people without a postal address with street, postal"
        " code and city, like the defined search",
    )
    primary_contact: str | None = Field(default=None, description="Short name")
    projects_or_deals_since: dt.date | None = Field(
        default=None,
        description="Only contacts of projects or deals created since the date,"
        " like the defined search of the web interface (5 years)",
    )


def _group(value):
    """The group with this title (titles are unique), otherwise the group
    with this ID, or ``None``

    Titles come first so that groups with numeric titles (e.g. 2026) can be
    found, every group can be found by its title."""
    groups = Group.objects.all()
    if group := groups.filter(title__iexact=value).first():
        return group
    if value.isascii() and value.isdigit():
        return groups.filter(pk=value).first()
    return None


def _query_error(field, msg):
    return ValidationError([{"loc": ["query", field], "msg": msg}])


@router.get("/contacts/people/", response=list[PersonListOut])
@paginate
def person_list(request, filters: Query[PersonFilter]):
    """Search people, e.g. the contact of a new project, or the members of a
    group like the list of people in the web interface"""
    active_groups = Group.objects.filter(is_archived=False)
    people = (
        Person.objects
        .select_related("organization", "primary_contact")
        .prefetch_related(
            Prefetch("groups", queryset=active_groups),
            Prefetch(
                "organization__groups",
                queryset=active_groups.filter(applies_to_organizations=True),
            ),
            "postaladdresses",
        )
        .order_by("given_name", "family_name", "pk")
    )
    if not filters.include_archived:
        people = people.active()
    if filters.organization:
        people = people.filter(organization=filters.organization)
    if filters.group:
        group = _group(filters.group)
        if not group:
            raise _query_error("group", _("Unknown group %r.") % filters.group)
        people = people.in_group(group)
    if filters.without_groups:
        people = people.without_groups()
    if filters.missing_postal_address:
        people = people.without_complete_postal_address()
    if filters.primary_contact:
        user = User.objects.by_short_name(filters.primary_contact).first()
        if not user:
            raise _query_error(
                "primary_contact", _("Unknown user %r.") % filters.primary_contact
            )
        people = people.filter(primary_contact=user)
    if since := filters.projects_or_deals_since:
        people = people.filter(recent_projects_or_deals("contact", since=since))
    if filters.q:
        people = people.search(filters.q)
    return Serialized(
        people,
        lambda person: (
            person_list_out(person, request)
            | {
                "primary_contact": person.primary_contact.get_short_name(),
                "groups": [group.title for group in person.all_groups()],
                "postal_address": _postal_address_out(person),
            }
        ),
    )


class PersonDuplicateOut(PersonOut):
    primary_contact: str
    email_addresses: list[str]


class DuplicatesOut(Schema):
    people: list[PersonDuplicateOut]


@router.get("/contacts/people/duplicates/", response=list[DuplicatesOut])
@paginate
def person_duplicates(request):
    """Groups of possible duplicates like in the web interface: people with
    the same name, or with the same email address and a common given or
    family name; archived people only with active people of their
    organization. The person to keep is usually the first (active, oldest)."""
    return [
        {
            "people": [
                person_list_out(person, request)
                | {
                    "primary_contact": person.primary_contact.get_short_name(),
                    "email_addresses": [
                        email.email for email in person.emailaddresses.all()
                    ],
                }
                for person in group
            ]
        }
        for group in possible_duplicates()
    ]


class SharedEmailOut(Schema):
    email: str
    organization: OrganizationOut | None
    is_organization_email: bool = Field(
        description="The central address of the organization, it's shown on its"
        " people and doesn't belong on them"
    )
    people: list[PersonSummary]


def _shared_details(details, value, central):
    """``(value, organization, is_central, people)`` of contact details of
    several active people of the same organization (or without one), or the
    central value of their organization"""
    rows = defaultdict(list)
    for detail in (
        details
        .filter(person__is_archived=False)
        .select_related("person__organization")
        .order_by("person__given_name", "person__family_name", "person")
    ):
        person = detail.person
        key = (value(detail), person.organization_id)
        # Empty values would match organizations without a central value
        if key[0] and person not in rows[key]:
            rows[key].append(person)
    for (detail, _organization_id), people in sorted(
        rows.items(), key=lambda item: (item[0][0], item[0][1] or 0)
    ):
        organization = people[0].organization
        is_central = bool(organization and central(organization) == detail)
        if len(people) > 1 or is_central:
            yield detail, organization, is_central, people


def _shared_out(organization, people, request):
    return {
        "organization": organization_out(organization, request)
        if organization
        else None,
        "people": [person_summary(person, request) for person in people],
    }


@router.get("/contacts/people/shared-email-addresses/", response=list[SharedEmailOut])
@paginate
def shared_email_addresses(request):
    """Email addresses of several active people of the same organization (or
    without one), or the central address of their organization; usually
    generic addresses like info@ which belong to the organization"""
    return [
        {"email": email, "is_organization_email": is_central}
        | _shared_out(organization, people, request)
        for email, organization, is_central, people in _shared_details(
            EmailAddress.objects.all(),
            lambda detail: detail.email.strip().lower(),
            lambda organization: organization.email.strip().lower(),
        )
    ]


class SharedPhoneNumberOut(Schema):
    phone_number: str
    organization: OrganizationOut | None
    is_organization_phone_number: bool = Field(
        description="The central number of the organization, it's shown on its"
        " people and doesn't belong on them"
    )
    people: list[PersonSummary]


@router.get(
    "/contacts/people/shared-phone-numbers/", response=list[SharedPhoneNumberOut]
)
@paginate
def shared_phone_numbers(request):
    """Phone numbers of several active people of the same organization (or
    without one), or the central number of their organization; usually the
    reception, which belongs to the organization"""
    return [
        {"phone_number": number, "is_organization_phone_number": is_central}
        | _shared_out(organization, people, request)
        for number, organization, is_central, people in _shared_details(
            PhoneNumber.objects.all(),
            lambda detail: detail.phone_number,
            lambda organization: organization.phone_number,
        )
    ]


class OrganizationPostalAddressOut(Schema):
    id: int = Field(
        description="ID of one of the people's postal addresses, identifies the"
        " address when changing it"
    )
    value: str = Field(description="The address on one line")
    street: str
    house_number: str
    address_suffix: str
    postal_code: str
    city: str
    country: str = Field(description="ISO 3166-1 code, e.g. CH")
    postal_address_override: str
    people: list[PersonSummary]


class OrganizationDetail(OrganizationOut):
    is_private_person: bool
    notes: str
    email: str = Field(description="Central address, e.g. info@")
    accounts_payable_email: str = Field(
        description="Optional, for invoices and payment reminders"
    )
    phone_number: str = Field(
        description="Central number in E.164 format, e.g. the reception"
    )
    primary_contact: str
    groups: list[str]
    people: list[PersonSummary]
    postal_addresses: list[OrganizationPostalAddressOut] = Field(
        description="The distinct postal addresses of the active people, those of"
        " most people first"
    )


@router.get(
    "/contacts/organizations/{int:organization_id}/", response=OrganizationDetail
)
def organization_detail(request, organization_id: int):
    organization = get_object_or_404(
        Organization.objects.select_related("primary_contact"), pk=organization_id
    )
    return organization_out(organization, request) | {
        "is_private_person": organization.is_private_person,
        "notes": organization.notes,
        "email": organization.email,
        "accounts_payable_email": organization.accounts_payable_email,
        "phone_number": organization.phone_number,
        "primary_contact": organization.primary_contact.get_short_name(),
        "groups": [group.title for group in organization.groups.all()],
        "people": [
            person_summary(person, request) for person in organization.people.all()
        ],
        "postal_addresses": [
            address["fields"]
            | {
                "id": address["addresses"][0].pk,
                "value": address["line"],
                "people": [
                    person_summary(person, request) for person in address["people"]
                ],
            }
            for address in organization_postal_addresses(organization)
        ],
    }


class MergeIn(InputSchema):
    into: int = Field(description="ID of the person or organization to keep")


class OrganizationPatch(InputSchema):
    primary_contact: str | None = Field(
        default=None, description="Short name of an active user"
    )
    is_archived: bool | None = None
    email: str | None = Field(
        default=None,
        description="Central address, e.g. info@; remove it from the people"
        " of the organization, it's shown on them",
    )
    accounts_payable_email: str | None = Field(
        default=None, description="For invoices and payment reminders"
    )
    phone_number: str | None = Field(
        default=None,
        description="Central number, e.g. the reception; remove it from the"
        " people of the organization, it's shown on them",
    )


def _organization_detail_out(organization, request):
    return organization_detail(request, organization.pk)


@router.patch(
    "/contacts/organizations/{int:organization_id}/", response=OrganizationDetail
)
def organization_update(
    request,
    organization_id: int,
    data: OrganizationPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change the primary contact, the email addresses or the phone number
    of an organization or archive it. Archiving warns about active people (`archive-people`),
    ignoring the warning archives them too."""
    organization = get_object_or_404(Organization, pk=organization_id)
    archiving = data.is_archived and not organization.is_archived
    if (
        archiving
        and "archive-people" not in ignore_warnings
        and (warning := organization.archive_warning())
    ):
        raise ValidationError([
            {"loc": ["body", "data"], "msg": warning, "code": "archive-people"}
        ])
    if data.primary_contact is not None:
        user = (
            User.objects
            .by_short_name(data.primary_contact)
            .filter(is_active=True)
            .first()
        )
        if not user:
            raise ValidationError([
                {
                    "loc": ["body", "data", "primary_contact"],
                    "msg": _("Unknown or inactive user %r.") % data.primary_contact,
                }
            ])
        organization.primary_contact = user
    if data.is_archived is not None:
        organization.is_archived = data.is_archived
    for field in ["email", "accounts_payable_email", "phone_number"]:
        if (value := getattr(data, field)) is not None:
            setattr(organization, field, value.strip())
    errors = []
    full_clean(organization, ["body", "data"], errors)
    if errors:
        raise ValidationError(errors)
    with transaction.atomic():
        organization.save()
        if archiving:
            organization.archive_people()
        result = _organization_detail_out(organization, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


@router.post(
    "/contacts/organizations/{int:organization_id}/merge/",
    response=OrganizationDetail,
)
def organization_merge(
    request,
    organization_id: int,
    data: MergeIn,
    *,
    dry_run: DryRun = False,
):
    """Merge a duplicate organization into the organization to keep, like
    in the web interface: people, projects, deals, invoices and groups move,
    the duplicate is deleted. An inactive primary contact of the
    organization kept is replaced by the duplicate's active one."""
    duplicate = get_object_or_404(Organization, pk=organization_id)
    form = OrganizationMergeForm(
        {"into": data.into}, instance=duplicate, request=request, prefix=""
    )
    validate_form(form)
    with transaction.atomic():
        keep = form.save()
        result = _organization_detail_out(keep, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


class OrganizationPostalAddressIn(InputSchema):
    """Fields which aren't given keep their current value"""

    address: int = Field(description="ID from the organization's postal_addresses")
    street: str | None = None
    house_number: str | None = None
    address_suffix: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = Field(default=None, description="ISO 3166-1 code, e.g. CH")
    postal_address_override: str | None = None
    people: list[int] | None = Field(
        default=None,
        description="IDs of the people whose address changes, defaults to all who"
        " have it",
    )


@router.post(
    "/contacts/organizations/{int:organization_id}/postal-address/",
    response=OrganizationDetail,
)
def organization_change_postal_address(
    request,
    organization_id: int,
    data: OrganizationPostalAddressIn,
    *,
    dry_run: DryRun = False,
):
    """Change a postal address of several people of the organization at once,
    e.g. when it moves, like in the web interface"""
    organization = get_object_or_404(Organization, pk=organization_id)
    kwargs = {"instance": organization, "request": request, "address": data.address}
    values = form_data(OrganizationPostalAddressForm(**kwargs))
    values.update(data.dict(exclude={"address"}, exclude_none=True))
    form = OrganizationPostalAddressForm(values, **kwargs)
    validate_form(form)
    with transaction.atomic():
        form.save()
        result = _organization_detail_out(organization, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


class ContactDetail(Schema):
    id: int
    type: str = Field(
        description="Free text like work, mobile or private; the web interface"
        " suggests a localized default."
    )
    value: str


class PersonDetailOut(PersonOut):
    salutation: str
    notes: str
    primary_contact: str
    groups: list[str]
    email_addresses: list[ContactDetail]
    phone_numbers: list[ContactDetail]
    postal_addresses: list[ContactDetail]


@router.get("/contacts/people/{int:person_id}/", response=PersonDetailOut)
def person_detail(request, person_id: int):
    return person_out(
        get_object_or_404(
            Person.objects.select_related("organization", "primary_contact"),
            pk=person_id,
        ),
        request,
    )


def person_out(person, request):
    return person_list_out(person, request) | {
        "salutation": person.salutation,
        "notes": person.notes,
        "primary_contact": person.primary_contact.get_short_name(),
        "groups": [group.title for group in person.all_groups()],
        "email_addresses": [
            {"id": detail.id, "type": detail.type, "value": detail.email}
            for detail in person.emailaddresses.all()
        ],
        "phone_numbers": [
            {"id": detail.id, "type": detail.type, "value": detail.phone_number}
            for detail in person.phonenumbers.all()
        ],
        "postal_addresses": [
            {"id": detail.id, "type": detail.type, "value": detail.postal_address}
            for detail in person.postaladdresses.all()
        ],
    }


class EmailAddressIn(InputSchema):
    type: str | None = Field(
        default=None, max_length=40, description="E.g. work or private."
    )
    email: str


class PhoneNumberIn(InputSchema):
    type: str | None = Field(
        default=None, max_length=40, description="E.g. work, mobile or private."
    )
    phone_number: str = Field(
        description="Numbers without a country code are Swiss numbers."
    )


class PostalAddressIn(InputSchema):
    type: str | None = Field(
        default=None, max_length=40, description="E.g. work or private."
    )
    street: str
    house_number: str = ""
    address_suffix: str = Field(default="", description="E.g. a post office box.")
    postal_code: str
    city: str
    country: str = Field(default="CH", description="ISO 3166-1 alpha-2 code.")


class DetailsIn(InputSchema):
    email_addresses: list[EmailAddressIn] = []
    phone_numbers: list[PhoneNumberIn] = []
    postal_addresses: list[PostalAddressIn] = []


class PersonIn(DetailsIn):
    given_name: str = Field(min_length=1, max_length=100)
    family_name: str = Field(min_length=1, max_length=100)
    address: str = Field(
        default="",
        max_length=100,
        description="Mr./Ms./... in the language of the correspondence, e.g."
        " Herr or Frau.",
    )
    salutation: str = Field(
        min_length=1,
        max_length=100,
        description="Complete salutation in the language of the correspondence,"
        " e.g. Lieber Hans or Sehr geehrte Frau Muster.",
    )
    address_on_first_name_terms: bool = False
    notes: str = ""
    organization: int | None = Field(
        default=None,
        description="ID of an existing organization, find it with wb contacts search.",
    )
    new_organization: str | None = Field(
        default=None,
        min_length=1,
        description="Name of an organization to create with the person.",
    )
    primary_contact: str | None = Field(
        default=None,
        description="Short name, defaults to the current user. May be someone"
        " who isn't active anymore, e.g. who used to know the person, so that"
        " the contact can be found and reassigned later.",
    )


class PersonCreated(PersonDetailOut):
    id: int | None
    url: str | None


class PersonContext(Schema):
    import_schema: dict


@router.get("/contacts/people/context/", response=PersonContext)
def person_context(request):
    """The schema of a person to create, e.g. from an email signature"""
    return {"import_schema": PersonIn.model_json_schema()}


def _email_errors(data):
    """Email addresses are never used twice, central addresses of
    organizations are shown on their people already"""
    return [
        {
            "loc": ["body", "data", "email_addresses", index, "email"],
            "msg": _("Already used by %(person)s (ID %(id)s).")
            % {"person": existing.person, "id": existing.person_id},
        }
        for index, item in enumerate(data.email_addresses)
        for existing in EmailAddress.objects.filter(
            email__iexact=item.email.strip()
        ).select_related("person")
    ] + [
        {
            "loc": ["body", "data", "email_addresses", index, "email"],
            "msg": _(
                "The central address of %(organization)s (ID %(id)s), it's"
                " shown on its people."
            )
            % {"organization": organization, "id": organization.pk},
        }
        for index, item in enumerate(data.email_addresses)
        for organization in Organization.objects.filter(
            email__iexact=item.email.strip()
        )
    ]


def _duplicates(data, *, allow_duplicates):
    errors = _email_errors(data)

    def error(loc, msg):
        errors.append({"loc": ["body", "data", *loc], "msg": msg})

    if allow_duplicates:
        return errors
    for person in Person.objects.active().filter(
        given_name__iexact=data.given_name, family_name__iexact=data.family_name
    ):
        error(
            [],
            _(
                "%(person)s (ID %(id)s) exists already. Allow duplicates if this"
                " is someone else."
            )
            % {"person": person.name_with_organization, "id": person.pk},
        )
    # Archived people of the same organization (or without, like the new
    # one) should rather be unarchived
    archived = Person.objects.filter(
        is_archived=True,
        given_name__iexact=data.given_name,
        family_name__iexact=data.family_name,
    )
    if data.organization:
        archived = archived.filter(organization=data.organization)
    elif data.new_organization:
        archived = archived.filter(organization__name__iexact=data.new_organization)
    else:
        archived = archived.filter(organization__isnull=True)
    for person in archived.select_related("organization"):
        error(
            [],
            _(
                "%(person)s (ID %(id)s) has been archived. Unarchive them"
                " instead, or allow duplicates if this is someone else."
            )
            % {"person": person.name_with_organization, "id": person.pk},
        )
    if data.new_organization:
        for organization in Organization.objects.active().filter(
            name__iexact=data.new_organization
        ):
            error(
                ["new_organization"],
                _(
                    "%(organization)s (ID %(id)s) exists already. Use its ID or"
                    " allow duplicates."
                )
                % {"organization": organization, "id": organization.pk},
            )
    return errors


def _details(data, errors):
    """Validated, unsaved email addresses, phone numbers and postal
    addresses"""
    details = []
    seen = set()
    for key, model, items, field in [
        ("email_addresses", EmailAddress, data.email_addresses, "email"),
        ("phone_numbers", PhoneNumber, data.phone_numbers, "phone_number"),
        ("postal_addresses", PostalAddress, data.postal_addresses, None),
    ]:
        for index, item in enumerate(items):
            detail = model(**item.dict(exclude_none=True))
            full_clean(detail, ["body", "data", key, index], errors, exclude=["person"])
            details.append(detail)
            # Phone numbers have been normalized by full_clean()
            if field and (value := str(getattr(detail, field)).casefold()):
                if (key, value) in seen:
                    errors.append({
                        "loc": ["body", "data", key, index, field],
                        "msg": _("Listed twice."),
                    })
                seen.add((key, value))
    return details


def _central_phone_errors(details, organization_id):
    """The central phone number of the organization is shown on its people
    already"""
    organization = (
        Organization.objects.filter(pk=organization_id).first()
        if organization_id
        else None
    )
    if not (organization and organization.phone_number):
        return []
    return [
        {
            "loc": ["body", "data", "phone_numbers", index, "phone_number"],
            "msg": _(
                "The central phone number of %(organization)s (ID %(id)s), it's"
                " shown on its people."
            )
            % {"organization": organization, "id": organization.pk},
        }
        for index, detail in enumerate(d for d in details if isinstance(d, PhoneNumber))
        # Phone numbers have been normalized by full_clean()
        if detail.phone_number == organization.phone_number
    ]


def _save_details(person, details):
    for detail in details:
        detail.person = person
        detail.save()
    # Update the search index with the details
    person.save()


@router.post("/contacts/people/", response=PersonCreated)
def person_create(
    request,
    data: PersonIn,
    *,
    dry_run: DryRun = False,
    allow_duplicates: Query[
        bool,
        P(
            description="Create the person although someone with the same name or email address exists."
        ),
    ] = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Create a person with their contact details, and their organization
    if it doesn't exist yet

    Validated like in the web interface, warnings are errors here unless
    they are ignored. People with the same name, organizations with the same
    name and email addresses which are already in use are rejected; nothing
    is saved if anything is invalid or with ``dry_run``."""
    errors = []
    if data.organization and data.new_organization:
        errors.append({
            "loc": ["body", "data", "new_organization"],
            "msg": _("Either use an existing organization or create a new one."),
        })
    errors.extend(_duplicates(data, allow_duplicates=allow_duplicates))
    primary_contact = request.user
    if data.primary_contact:
        primary_contact = User.objects.by_short_name(data.primary_contact).first()
        if not primary_contact:
            errors.append({
                "loc": ["body", "data", "primary_contact"],
                "msg": _("Unknown user %r.") % data.primary_contact,
            })

    details = _details(data, errors)
    errors.extend(_central_phone_errors(details, data.organization))

    with transaction.atomic():
        organization = data.organization
        if data.new_organization:
            new = Organization(
                name=data.new_organization,
                primary_contact=primary_contact or request.user,
            )
            full_clean(new, ["body", "data", "new_organization"], errors)
            if not errors:
                new.save()
                organization = new.pk

        form = PersonForm(
            {
                "given_name": data.given_name,
                "family_name": data.family_name,
                "address": data.address,
                "salutation": data.salutation,
                "address_on_first_name_terms": data.address_on_first_name_terms,
                "notes": data.notes,
                "organization": organization or "",
                "primary_contact": request.user.pk,
            },
            request=request,
        )
        try:
            validate_form(form, ignore_warnings=ignore_warnings)
        except ValidationError as exc:
            errors.extend(exc.errors)
        if errors:
            # Rolls back the new organization
            raise ValidationError(errors)

        person = form.save()
        if primary_contact != request.user:
            # The form only offers active users
            person.primary_contact = primary_contact
            person.save(update_fields=["primary_contact"])
        _save_details(person, details)

        result = person_out(person, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
    return result


@router.post("/contacts/people/{int:person_id}/details/", response=PersonCreated)
def person_add_details(
    request, person_id: int, data: DetailsIn, *, dry_run: DryRun = False
):
    """Add email addresses, phone numbers and postal addresses to a person

    Never changes or removes existing details. Email addresses which are
    already in use and phone numbers the person has already are rejected."""
    person = get_object_or_404(
        Person.objects.select_related("organization", "primary_contact"), pk=person_id
    )
    errors = _email_errors(data)
    details = _details(data, errors)
    errors.extend(_central_phone_errors(details, person.organization_id))
    numbers = set(person.phonenumbers.values_list("phone_number", flat=True))
    errors.extend(
        {
            "loc": ["body", "data", "phone_numbers", index, "phone_number"],
            "msg": _("%(person)s has this phone number already.") % {"person": person},
        }
        for index, detail in enumerate(d for d in details if isinstance(d, PhoneNumber))
        # Phone numbers have been normalized by full_clean()
        if detail.phone_number in numbers
    )
    if errors:
        raise ValidationError(errors)

    with transaction.atomic():
        _save_details(person, details)
        result = person_out(person, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


class PersonPatch(InputSchema):
    """Fields which aren't given are left alone"""

    primary_contact: str | None = Field(
        default=None, description="Short name of an active user"
    )
    add_groups: list[str] = Field(
        default=[],
        description="Titles or IDs of active groups. Groups which apply to"
        " organizations are added to the organization, like in the person form.",
    )
    remove_groups: list[str] = Field(
        default=[],
        description="Titles or IDs of groups. Groups which apply to"
        " organizations are removed from the organization, so all its people"
        " lose them.",
    )
    remove_email_addresses: list[str] = Field(
        default=[],
        description="Email addresses to remove, e.g. generic ones like info@"
        " which belong to the organization",
    )
    remove_phone_numbers: list[str] = Field(
        default=[],
        description="Phone numbers to remove, e.g. the reception which belongs"
        " to the organization",
    )
    remove_postal_addresses: list[int] = Field(
        default=[],
        description="IDs of postal addresses to remove, e.g. old ones of the"
        " organization",
    )
    organization: int | None = Field(
        default=None,
        description="ID of the organization, e.g. the new employer of someone"
        " who left; null removes the person from their organization",
    )
    is_archived: bool | None = None


def _email_addresses_to_remove(person, values, error):
    """The person's email addresses matching the values (case-insensitive)"""
    remove = []
    for index, value in enumerate(values):
        emails = [
            email
            for email in person.emailaddresses.all()
            if email.email.strip().lower() == value.strip().lower()
        ]
        if emails:
            remove.extend(emails)
        else:
            error(
                ["remove_email_addresses", index],
                _("The person has no email address %r.") % value,
            )
    return remove


def _phone_numbers_to_remove(person, values, error):
    """The person's phone numbers matching the values (normalized)"""
    remove = []
    for index, value in enumerate(values):
        number = normalize_phone_number(value, "phone_number", {})
        numbers = [
            detail
            for detail in person.phonenumbers.all()
            if detail.phone_number == number
        ]
        if numbers:
            remove.extend(numbers)
        else:
            error(
                ["remove_phone_numbers", index],
                _("The person has no phone number %r.") % value,
            )
    return remove


def _postal_addresses_to_remove(person, ids, error):
    addresses = {address.pk: address for address in person.postaladdresses.all()}
    for index, pk in enumerate(ids):
        if pk not in addresses:
            error(
                ["remove_postal_addresses", index],
                _("The person has no postal address with the ID %r.") % pk,
            )
    return [addresses[pk] for pk in ids if pk in addresses]


def _groups_to_change(person, data, error):
    """The groups to add to and to remove from the person"""
    current = {group.pk for group in person.all_groups()}
    add, remove = [], []
    for key, values, target in [
        ("add_groups", data.add_groups, add),
        ("remove_groups", data.remove_groups, remove),
    ]:
        for index, value in enumerate(values):
            group = _group(value)
            if not group:
                error([key, index], _("Unknown group %r.") % value)
            elif key == "add_groups" and group.is_archived and group.pk not in current:
                # Like the form, which only offers archived groups to members
                error([key, index], _("The group %r is archived.") % group.title)
            else:
                target.append(group)
    return add, remove


def _move_to_organization(person, data, error):
    """Sets the person's new organization (or none), returns whether it
    changes"""
    if (
        "organization" not in data.model_fields_set
        or data.organization == person.organization_id
    ):
        return False
    if data.organization is None:
        person.organization = None
    elif organization := Organization.objects.filter(pk=data.organization).first():
        person.organization = organization
    else:
        error(["organization"], _("Unknown organization %r.") % data.organization)
    return True


@router.patch("/contacts/people/{int:person_id}/", response=PersonDetailOut)
def person_update(
    request,
    person_id: int,
    data: PersonPatch,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Change the primary contact, the organization and the groups of a
    person, remove email addresses, phone numbers and postal addresses or
    archive them, with the rules of the person form; contact details are
    added with ``details/``. Archiving the
    last active person of an organization without open projects or deals
    archives the organization too, unarchiving a person unarchives their
    organization, so does moving an active person into it. Moving the
    contact of projects, deals or invoices is a warning
    (``organization-update``), they keep their customer and contact. Groups
    which apply to organizations stay with the previous organization."""
    person = get_object_or_404(
        Person.objects.select_related("organization"), pk=person_id
    )
    errors = []

    def error(loc, msg):
        errors.append({"loc": ["body", "data", *loc], "msg": msg})

    add, remove = _groups_to_change(person, data, error)
    if data.primary_contact is not None:
        user = (
            User.objects
            .by_short_name(data.primary_contact)
            .filter(is_active=True)
            .first()
        )
        if user:
            person.primary_contact = user
        else:
            error(
                ["primary_contact"],
                _("Unknown or inactive user %r.") % data.primary_contact,
            )
    remove_emails = _email_addresses_to_remove(
        person, data.remove_email_addresses, error
    )
    remove_phones = _phone_numbers_to_remove(person, data.remove_phone_numbers, error)
    remove_addresses = _postal_addresses_to_remove(
        person, data.remove_postal_addresses, error
    )
    moving = _move_to_organization(person, data, error)
    if errors:
        raise ValidationError(errors)
    if (
        moving
        and "organization-update" not in ignore_warnings
        and (warning := organization_update_warning(person))
    ):
        raise ValidationError([
            {"loc": ["body", "data"], "msg": warning, "code": "organization-update"}
        ])

    archival_changed = (
        data.is_archived is not None and data.is_archived != person.is_archived
    )
    if data.is_archived is not None:
        person.is_archived = data.is_archived
    with transaction.atomic():
        for detail in [*remove_emails, *remove_phones, *remove_addresses]:
            detail.delete()
        # Also updates the full text search
        person.save()
        if archival_changed:
            update_organization_archival(person)
        elif moving:
            unarchive_organization(person)
        for group in add:
            person.add_to_group(group)
        for group in remove:
            person.remove_from_group(group)
        person = Person.objects.select_related("organization", "primary_contact").get(
            pk=person.pk
        )
        result = person_out(person, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


@router.post("/contacts/people/{int:person_id}/merge/", response=PersonDetailOut)
def person_merge(
    request,
    person_id: int,
    data: MergeIn,
    *,
    dry_run: DryRun = False,
    ignore_warnings: list[str] = IGNORE_WARNINGS,
):
    """Merge a duplicate into the person to keep, like in the web interface: projects, deals, invoices, the linked user, contact
    details (except those the person to keep has already) and groups move,
    notes are appended; the duplicate is deleted

    Merging into someone of another organization is a warning
    (``other-organization``) if the duplicate is the contact of projects,
    deals or invoices."""
    duplicate = get_object_or_404(Person, pk=person_id)
    keep = Person.objects.filter(pk=data.into).first()
    if not keep:
        raise ValidationError([
            {
                "loc": ["body", "data", "into"],
                "msg": _("Unknown person %r.") % data.into,
            }
        ])
    form = PersonMergeForm(
        {"into": keep.pk}, instance=duplicate, request=request, prefix=""
    )
    validate_form(form, ignore_warnings=ignore_warnings)
    with transaction.atomic():
        form.save()
        keep = Person.objects.select_related("organization", "primary_contact").get(
            pk=keep.pk
        )
        result = person_out(keep, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


class GroupOut(Schema):
    id: int
    url: str
    title: str
    is_archived: bool
    applies_to_organizations: bool
    is_pinned: bool = Field(description="Pinned groups are listed first")
    people_count: int | None = Field(
        default=None, description="Active people, also through organizations"
    )
    organizations_count: int | None = Field(
        default=None, description="Active organizations"
    )


class GroupFilter(Schema):
    q: SearchQuery = ""
    include_archived: bool = Field(default=False, description="Also archived groups.")


def _group_out(group, request):
    return {
        "id": group.id,
        "url": request.build_absolute_uri(group.get_absolute_url()),
        "title": group.title,
        "is_archived": group.is_archived,
        "applies_to_organizations": group.applies_to_organizations,
        "is_pinned": group.is_pinned,
        "people_count": getattr(group, "people_count", None),
        "organizations_count": getattr(group, "organizations_count", None),
    }


@router.get("/contacts/groups/", response=list[GroupOut])
@paginate
def group_list(request, filters: Query[GroupFilter]):
    """Groups with their active members, like the list of groups in the web
    interface"""
    form = GroupSearchForm(
        {"q": filters.q, "s": "all" if filters.include_archived else ""},
        request=request,
    )
    form.is_valid()
    return Serialized(
        form.filter(Group.objects.all()), lambda group: _group_out(group, request)
    )


class GroupIn(InputSchema):
    title: str = Field(min_length=1, max_length=100)
    applies_to_organizations: bool = False


class GroupPatch(InputSchema):
    """Fields which aren't given are left alone"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    applies_to_organizations: bool | None = Field(
        default=None,
        description="Turning it on moves the people's memberships to their"
        " organizations, like in the web interface.",
    )
    is_pinned: bool | None = Field(
        default=None, description="Pinned groups are listed first"
    )
    is_archived: bool | None = None


def _save_group(request, group, values, *, dry_run):
    """Validate with the group form of the web interface, which also keeps
    titles unique because the APIs find groups by their title"""
    # The form has a prefix (it's shown in modals)
    prefix = GroupForm(request=request).add_prefix
    form = GroupForm(
        {prefix(name): value for name, value in values.items()},
        instance=group,
        request=request,
    )
    if not form.is_valid(ignore_warnings=True):
        raise_form_errors(form)
    with transaction.atomic():
        group = form.save()
        result = _group_out(group, request)
        if dry_run:
            transaction.set_rollback(True)
    return result


def _group_values(group, request):
    """The group's current values, keyed by field name"""
    form = GroupForm(instance=group, request=request)
    return {name: form[name].value() for name in form.fields}


@router.post("/contacts/groups/", response=GroupOut)
def group_create(request, data: GroupIn, *, dry_run: DryRun = False):
    """Create a group, e.g. for a mailing"""
    group = Group()
    values = _group_values(group, request) | data.dict()
    return _save_group(request, group, values, dry_run=dry_run)


@router.patch("/contacts/groups/{int:group_id}/", response=GroupOut)
def group_update(request, group_id: int, data: GroupPatch, *, dry_run: DryRun = False):
    """Rename, pin or archive a group, or let it apply to organizations"""
    group = get_object_or_404(Group, pk=group_id)
    values = _group_values(group, request) | data.dict(
        exclude_unset=True, exclude_none=True
    )
    return _save_group(request, group, values, dry_run=dry_run)


class SuggestionOut(Schema):
    short_name: str
    source: Literal["project", "deal", "organization_project", "organization_deal"]
    title: str = Field(description="The project or deal")
    url: str
    created_at: dt.datetime


class ReassignSuggestionOut(Schema):
    person: PersonOut
    primary_contact: str
    suggestion: SuggestionOut | None


class ReassignFilter(Schema):
    primary_contact: str | None = Field(
        default=None,
        description="Short name; defaults to all users who aren't active anymore",
    )
    since: dt.date | None = Field(
        default=None, description="Only projects and deals created since the date"
    )


def _user(short_name, loc, *, active_only=False):
    users = User.objects.by_short_name(short_name)
    if active_only:
        users = users.filter(is_active=True)
    if user := users.first():
        return user
    raise ValidationError([
        {
            "loc": loc,
            "msg": (
                _("Unknown or inactive user %r.")
                if active_only
                else _("Unknown user %r.")
            )
            % short_name,
        }
    ])


def _suggestion_out(suggestion, request):
    if not suggestion:
        return None
    item = suggestion["item"]
    return {
        "short_name": suggestion["user"].get_short_name(),
        "source": suggestion["source"],
        "title": str(item),
        "url": request.build_absolute_uri(item.get_absolute_url()),
        "created_at": item.created_at,
    }


@router.get("/contacts/people/reassign/", response=list[ReassignSuggestionOut])
@paginate
def person_reassign_suggestions(request, filters: Query[ReassignFilter]):
    """Active people whose primary contact isn't active anymore (or the given
    user), with a suggestion for a new primary contact: the lead of the
    latest project or the owner of the latest deal, the person's own before
    those of their organization"""
    people = (
        Person.objects
        .active()
        .select_related("organization", "primary_contact")
        .order_by("primary_contact", "given_name", "family_name", "pk")
    )
    if filters.primary_contact:
        people = people.filter(
            primary_contact=_user(filters.primary_contact, ["query", "primary_contact"])
        )
    else:
        people = people.filter(primary_contact__is_active=False)
    people = list(people)
    suggestions = primary_contact_suggestions(people, since=filters.since)
    return [
        {
            "person": person_list_out(person, request),
            "primary_contact": person.primary_contact.get_short_name(),
            "suggestion": _suggestion_out(suggestions.get(person.pk), request),
        }
        for person in people
    ]


class ReassignIn(InputSchema):
    from_: str | None = Field(
        default=None,
        alias="from",
        description="Short name, also of inactive users; with suggested it"
        " defaults to everyone who isn't active anymore",
    )
    to: str | None = Field(default=None, description="Short name of an active user")
    suggested: bool = Field(
        default=False,
        description="Reassign to the suggestions instead (see the GET endpoint);"
        " people without a suggestion stay",
    )
    since: dt.date | None = Field(
        default=None, description="With suggested: only projects and deals since"
    )


class ReassignChange(Schema):
    id: int
    full_name: str
    to: str


class ReassignOut(Schema):
    changes: list[ReassignChange]


@router.post("/contacts/people/reassign/", response=ReassignOut)
def person_reassign(request, data: ReassignIn, *, dry_run: DryRun = False):
    """Reassign the active people of a user to another active user or to the
    suggestions, e.g. when someone left"""
    if bool(data.to) == data.suggested:
        raise ValidationError([
            {
                "loc": ["body", "data", "to"],
                "msg": _("Either reassign to someone or to the suggestions."),
            }
        ])
    if data.to and not data.from_:
        raise ValidationError([
            {"loc": ["body", "data", "from"], "msg": _("This field is required.")}
        ])
    people = Person.objects.active().select_related("primary_contact").order_by("pk")
    if data.from_:
        people = people.filter(
            primary_contact=_user(data.from_, ["body", "data", "from"])
        )
    else:
        people = people.filter(primary_contact__is_active=False)
    people = list(people)
    if data.to:
        user = _user(data.to, ["body", "data", "to"], active_only=True)
        targets = {person.pk: user for person in people}
    else:
        targets = {
            pk: suggestion["user"]
            for pk, suggestion in primary_contact_suggestions(
                people, since=data.since
            ).items()
        }
    changes = []
    with transaction.atomic():
        for person in people:
            if (user := targets.get(person.pk)) and user != person.primary_contact:
                person.primary_contact = user
                person.save(update_fields=["primary_contact"])
                changes.append({
                    "id": person.pk,
                    "full_name": person.full_name,
                    "to": user.get_short_name(),
                })
        if dry_run:
            transaction.set_rollback(True)
    return {"changes": changes}
