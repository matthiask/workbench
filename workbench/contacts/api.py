import datetime as dt
from typing import Literal

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Query, Router, Schema
from ninja.errors import ValidationError
from ninja.pagination import paginate

from workbench.accounts.models import User
from workbench.contacts.forms import (
    GroupForm,
    GroupSearchForm,
    PersonForm,
    recent_projects_or_deals,
)
from workbench.contacts.models import (
    EmailAddress,
    Group,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.tools.api import (
    Serialized,
    form_errors,
    full_clean,
    raise_form_errors,
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
        "organization": organization_out(person.organization, request)
        if person.organization
        else None
    }


class OrganizationFilter(Schema):
    q: str = ""
    include_archived: bool = False


@router.get("/contacts/organizations/", response=list[OrganizationOut])
@paginate
def organization_list(request, filters: Query[OrganizationFilter]):
    """Search organizations, e.g. the customer of a new project"""
    organizations = Organization.objects.order_by("name", "pk")
    if not filters.include_archived:
        organizations = organizations.active()
    if filters.q:
        organizations = organizations.search(filters.q)
    return Serialized(
        organizations, lambda organization: organization_out(organization, request)
    )


class PersonFilter(OrganizationFilter):
    organization: int | None = None
    group: str | None = Field(
        default=None,
        description="ID or title of a group; also people who are in it through"
        " their organization",
    )
    without_groups: bool = Field(
        default=False, description="Only people in no active group"
    )
    primary_contact: str | None = Field(default=None, description="Short name")
    projects_or_deals_since: dt.date | None = Field(
        default=None,
        description="Only contacts of projects or deals created since the date,"
        " like the defined search of the web interface (5 years)",
    )


def _group(value):
    """A group by its ID or title"""
    groups = Group.objects.all()
    return (
        groups.filter(pk=value).first()
        if value.isdigit()
        else groups.filter(title__iexact=value).first()
    )


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
    if filters.primary_contact:
        user = User.objects.filter(_short_name__iexact=filters.primary_contact).first()
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


class OrganizationDetail(OrganizationOut):
    is_private_person: bool
    notes: str
    primary_contact: str
    groups: list[str]
    people: list[PersonSummary]


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
        "primary_contact": organization.primary_contact.get_short_name(),
        "groups": [group.title for group in organization.groups.all()],
        "people": [
            person_summary(person, request) for person in organization.people.all()
        ],
    }


class ContactDetail(Schema):
    type: str
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
            {"type": detail.type, "value": detail.email}
            for detail in person.emailaddresses.all()
        ],
        "phone_numbers": [
            {"type": detail.type, "value": detail.phone_number}
            for detail in person.phonenumbers.all()
        ],
        "postal_addresses": [
            {"type": detail.type, "value": detail.postal_address}
            for detail in person.postaladdresses.all()
        ],
    }


class EmailAddressIn(Schema):
    type: str | None = Field(
        default=None, max_length=40, description="E.g. work or private."
    )
    email: str


class PhoneNumberIn(Schema):
    type: str | None = Field(
        default=None, max_length=40, description="E.g. work, mobile or private."
    )
    phone_number: str = Field(
        description="Numbers without a country code are Swiss numbers."
    )


class PostalAddressIn(Schema):
    type: str | None = Field(
        default=None, max_length=40, description="E.g. work or private."
    )
    street: str
    house_number: str = ""
    address_suffix: str = Field(default="", description="E.g. a post office box.")
    postal_code: str
    city: str
    country: str = Field(default="CH", description="ISO 3166-1 alpha-2 code.")


class DetailsIn(Schema):
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
    """Email addresses are never used twice"""
    return [
        {
            "loc": ["body", "data", "email_addresses", index, "email"],
            "msg": _("Already used by %(person)s (ID %(id)s).")
            % {"person": existing.person, "id": existing.person_id},
        }
        for index, item in enumerate(data.email_addresses)
        for existing in EmailAddress.objects.filter(
            email__iexact=item.email
        ).select_related("person")
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
    for key, model, items in [
        ("email_addresses", EmailAddress, data.email_addresses),
        ("phone_numbers", PhoneNumber, data.phone_numbers),
        ("postal_addresses", PostalAddress, data.postal_addresses),
    ]:
        for index, item in enumerate(items):
            detail = model(**item.dict(exclude_none=True))
            full_clean(detail, ["body", "data", key, index], errors, exclude=["person"])
            details.append(detail)
    return details


def _save_details(person, details):
    for detail in details:
        detail.person = person
        detail.save()
    # Update the search index with the details
    person.save()


@router.post("/contacts/people/", response=PersonCreated)
def person_create(
    request, data: PersonIn, *, dry_run: bool = False, allow_duplicates: bool = False
):
    """Create a person with their contact details, and their organization
    if it doesn't exist yet

    Validated like in the web interface, warnings are errors here. People
    with the same name, organizations with the same name and email addresses
    which are already in use are rejected; nothing is saved if anything is
    invalid or with ``dry_run``."""
    errors = []
    if data.organization and data.new_organization:
        errors.append({
            "loc": ["body", "data", "new_organization"],
            "msg": _("Either use an existing organization or create a new one."),
        })
    errors.extend(_duplicates(data, allow_duplicates=allow_duplicates))

    details = _details(data, errors)

    with transaction.atomic():
        organization = data.organization
        if data.new_organization:
            new = Organization(name=data.new_organization, primary_contact=request.user)
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
        if not form.is_valid():
            errors.extend(form_errors(form))
        if errors:
            # Rolls back the new organization
            raise ValidationError(errors)

        person = form.save()
        _save_details(person, details)

        result = person_out(person, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
    return result


@router.post("/contacts/people/{int:person_id}/details/", response=PersonCreated)
def person_add_details(
    request, person_id: int, data: DetailsIn, *, dry_run: bool = False
):
    """Add email addresses, phone numbers and postal addresses to a person

    Never changes or removes existing details. Email addresses which are
    already in use and phone numbers the person has already are rejected."""
    person = get_object_or_404(
        Person.objects.select_related("organization", "primary_contact"), pk=person_id
    )
    errors = _email_errors(data)
    details = _details(data, errors)
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


class PersonPatch(Schema):
    """Fields which aren't given are left alone"""

    primary_contact: str | None = Field(
        default=None, description="Short name of an active user"
    )
    add_groups: list[str] = Field(
        default=[],
        description="IDs or titles of active groups. Groups which apply to"
        " organizations are added to the organization, like in the person form.",
    )
    remove_groups: list[str] = Field(
        default=[],
        description="IDs or titles of groups. Groups which apply to"
        " organizations are removed from the organization too.",
    )
    is_archived: bool | None = None


@router.patch("/contacts/people/{int:person_id}/", response=PersonDetailOut)
def person_update(request, person_id: int, data: PersonPatch, *, dry_run: bool = False):
    """Change the primary contact and the groups of a person or archive them,
    with the rules of the person form; contact details are added with
    ``details/``"""
    person = get_object_or_404(
        Person.objects.select_related("organization"), pk=person_id
    )
    errors = []

    def error(loc, msg):
        errors.append({"loc": ["body", "data", *loc], "msg": msg})

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
    if data.primary_contact is not None:
        user = User.objects.filter(
            is_active=True, _short_name__iexact=data.primary_contact
        ).first()
        if user:
            person.primary_contact = user
        else:
            error(
                ["primary_contact"],
                _("Unknown or inactive user %r.") % data.primary_contact,
            )
    if errors:
        raise ValidationError(errors)

    if data.is_archived is not None:
        person.is_archived = data.is_archived
    with transaction.atomic():
        person.save()
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


class GroupOut(Schema):
    id: int
    url: str
    title: str
    is_archived: bool
    applies_to_organizations: bool
    people_count: int | None = Field(
        default=None, description="Active people, also through organizations"
    )
    organizations_count: int | None = Field(
        default=None, description="Active organizations"
    )


class GroupFilter(Schema):
    q: str = ""
    s: Literal["", "archived", "all"] = Field(
        default="", description="Active groups by default"
    )


def _group_out(group, request):
    return {
        "id": group.id,
        "url": request.build_absolute_uri(group.get_absolute_url()),
        "title": group.title,
        "is_archived": group.is_archived,
        "applies_to_organizations": group.applies_to_organizations,
        "people_count": getattr(group, "people_count", None),
        "organizations_count": getattr(group, "organizations_count", None),
    }


@router.get("/contacts/groups/", response=list[GroupOut])
@paginate
def group_list(request, filters: Query[GroupFilter]):
    """Groups with their active members, like the list of groups in the web
    interface"""
    form = GroupSearchForm(filters.dict(), request=request)
    form.is_valid()
    return Serialized(
        form.filter(Group.objects.all()), lambda group: _group_out(group, request)
    )


class GroupIn(Schema):
    title: str = Field(min_length=1, max_length=100)
    applies_to_organizations: bool = False


class GroupPatch(Schema):
    """Fields which aren't given are left alone"""

    title: str | None = Field(default=None, min_length=1, max_length=100)
    applies_to_organizations: bool | None = Field(
        default=None,
        description="Turning it on moves the people's memberships to their"
        " organizations, like in the web interface.",
    )
    is_archived: bool | None = None


def _save_group(request, group, values, *, dry_run):
    """Validate with the group form of the web interface; titles are unique
    because the APIs find groups by their title"""
    # The form has a prefix (it's shown in modals)
    prefix = GroupForm(request=request).add_prefix
    form = GroupForm(
        {prefix(name): value for name, value in values.items()},
        instance=group,
        request=request,
    )
    if not form.is_valid(ignore_warnings=True):
        raise_form_errors(form)
    if (
        Group.objects
        .filter(title__iexact=form.cleaned_data["title"])
        .exclude(pk=group.pk)
        .exists()
    ):
        raise ValidationError([
            {
                "loc": ["body", "data", "title"],
                "msg": _("A group with this title exists already."),
            }
        ])
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
def group_create(request, data: GroupIn, *, dry_run: bool = False):
    """Create a group, e.g. for a mailing"""
    group = Group()
    values = _group_values(group, request) | data.dict()
    return _save_group(request, group, values, dry_run=dry_run)


@router.patch("/contacts/groups/{int:group_id}/", response=GroupOut)
def group_update(request, group_id: int, data: GroupPatch, *, dry_run: bool = False):
    """Rename or archive a group, or let it apply to organizations"""
    group = get_object_or_404(Group, pk=group_id)
    values = _group_values(group, request) | data.dict(exclude_unset=True)
    return _save_group(request, group, values, dry_run=dry_run)
