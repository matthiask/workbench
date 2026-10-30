from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from ninja import Field, Router, Schema
from ninja.errors import ValidationError

from workbench.contacts.forms import PersonForm
from workbench.contacts.models import (
    EmailAddress,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.tools.api import form_errors, full_clean


router = Router(tags=["contacts"])


class OrganizationOut(Schema):
    id: int
    name: str
    is_archived: bool


class PersonOut(Schema):
    id: int
    full_name: str
    organization: OrganizationOut | None
    is_archived: bool


@router.get("/contacts/organizations/", response=list[OrganizationOut])
def organization_list(request, q: str = "", *, include_archived: bool = False):
    """Search organizations, e.g. the customer of a new project"""
    organizations = Organization.objects.all()
    if not include_archived:
        organizations = organizations.active()
    if q:
        organizations = organizations.search(q)
    return organizations[:50]


@router.get("/contacts/people/", response=list[PersonOut])
def person_list(
    request,
    q: str = "",
    organization: int | None = None,
    *,
    include_archived: bool = False,
):
    """Search people, e.g. the contact of a new project"""
    people = Person.objects.select_related("organization")
    if not include_archived:
        people = people.active()
    if organization:
        people = people.filter(organization=organization)
    if q:
        people = people.search(q)
    return people[:50]


class PersonSummary(Schema):
    id: int
    full_name: str
    is_archived: bool


class OrganizationDetail(OrganizationOut):
    url: str
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
    return {
        "id": organization.id,
        "url": request.build_absolute_uri(organization.get_absolute_url()),
        "name": organization.name,
        "is_archived": organization.is_archived,
        "is_private_person": organization.is_private_person,
        "notes": organization.notes,
        "primary_contact": organization.primary_contact.get_short_name(),
        "groups": [group.title for group in organization.groups.all()],
        "people": organization.people.all(),
    }


class ContactDetail(Schema):
    type: str
    value: str


class PersonDetailOut(PersonOut):
    url: str
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
    return {
        "id": person.id,
        "url": request.build_absolute_uri(person.get_absolute_url()),
        "full_name": person.full_name,
        "organization": person.organization,
        "is_archived": person.is_archived,
        "salutation": person.salutation,
        "notes": person.notes,
        "primary_contact": person.primary_contact.get_short_name(),
        "groups": [group.title for group in person.groups.all()],
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


class PersonIn(Schema):
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
    email_addresses: list[EmailAddressIn] = []
    phone_numbers: list[PhoneNumberIn] = []
    postal_addresses: list[PostalAddressIn] = []


class PersonCreated(PersonDetailOut):
    id: int | None
    url: str | None


class PersonContext(Schema):
    import_schema: dict


@router.get("/contacts/people/context/", response=PersonContext)
def person_context(request):
    """The schema of a person to create, e.g. from an email signature"""
    return {"import_schema": PersonIn.model_json_schema()}


def _duplicates(data, *, allow_duplicates):
    errors = []

    def error(loc, msg):
        errors.append({"loc": ["body", "data", *loc], "msg": msg})

    for index, item in enumerate(data.email_addresses):
        for existing in EmailAddress.objects.filter(
            email__iexact=item.email
        ).select_related("person"):
            error(
                ["email_addresses", index, "email"],
                _("Already used by %(person)s (ID %(id)s).")
                % {"person": existing.person, "id": existing.person_id},
            )
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


def _details(data):
    """Unsaved email addresses, phone numbers and postal addresses"""
    for key, model, items in [
        ("email_addresses", EmailAddress, data.email_addresses),
        ("phone_numbers", PhoneNumber, data.phone_numbers),
        ("postal_addresses", PostalAddress, data.postal_addresses),
    ]:
        for index, item in enumerate(items):
            fields = item.dict(exclude_none=True)
            yield ["body", "data", key, index], model(**fields)


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

    details = list(_details(data))
    for loc, detail in details:
        full_clean(detail, loc, errors, exclude=["person"])

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
        for _loc, detail in details:
            detail.person = person
            detail.save()
        # Update the search index with the details
        person.save()

        result = person_out(person, request)
        if dry_run:
            transaction.set_rollback(True)
            result |= {"id": None, "url": None}
    return result
