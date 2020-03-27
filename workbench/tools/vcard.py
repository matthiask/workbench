from vobject import vCard, vcard


def person_to_vcard(person):
    v = vCard()
    v.add("n")
    v.n.value = vcard.Name(
        family=person.family_name, given=person.given_name, additional=person.address
    )
    v.add("fn")
    v.fn.value = person.full_name

    if person.organization and not person.organization.is_private_person:
        v.add("org").value = [person.organization.name]
    if person.date_of_birth:
        v.add("bday").value = person.date_of_birth.isoformat()
    if person.notes:
        v.add("note").value = person.notes

    for phone_number in person.phonenumbers.all():
        attr = v.add("tel")
        attr.value = phone_number.phone_number
        attr.type_param = phone_number.type
    for email in person.emailaddresses.all():
        attr = v.add("email")
        attr.value = email.email
        attr.type_param = email.type
    for address in person.postaladdresses.all():
        attr = v.add("adr")
        if address.postal_address_override:
            attr.value = address.postal_address_override
        else:
            attr.value = vcard.Address(
                street="{} {}\n{}".format(
                    address.street, address.house_number, address.address_suffix
                ),
                code=address.postal_code,
                city=address.city,
                country=address.country.name,
                # region=
            )
        attr.type_param = address.type
    return v


def test():
    from workbench.contacts.models import Person

    p = Person.objects.get(pk=2)

    print(person_to_vcard(p).serialize())
