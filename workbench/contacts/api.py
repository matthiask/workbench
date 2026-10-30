from django.shortcuts import get_object_or_404
from ninja import Router, Schema

from workbench.contacts.models import Organization, Person


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


@router.get("/contacts/organizations/{organization_id}/", response=OrganizationDetail)
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


@router.get("/contacts/people/{person_id}/", response=PersonDetailOut)
def person_detail(request, person_id: int):
    person = get_object_or_404(
        Person.objects.select_related("organization", "primary_contact"), pk=person_id
    )
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
