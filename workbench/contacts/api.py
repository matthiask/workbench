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
