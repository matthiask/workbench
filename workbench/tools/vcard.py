import re

from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseRedirect
from django.utils.translation import gettext as _

from vobject import vCard, vcard


def person_to_vcard(person):
    v = vCard()
    v.add("n")
    v.n.value = vcard.Name(family=person.family_name, given=person.given_name)
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
            attr.value = vcard.Address(street=address.postal_address_override)
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


def is_ios(user_agent):
    return re.search(r"(ios|ipad|iphone)", user_agent, re.I)


def render_vcard_response(request, vcard, subject=""):
    if is_ios(request.META.get("HTTP_USER_AGENT") or ""):
        mail = EmailMultiAlternatives(
            ": ".join(filter(None, ("vCard", subject))), "", to=[request.user.email]
        )
        mail.attach("vcard.vcf", vcard, "text/x-vCard")
        mail.send(fail_silently=True)
        messages.success(
            request,
            _(
                "You seem to be using iOS. iOS does not support directly opening"
                " vCard files. Instead, you have been sent an email containing"
                " the vCard to your email address, %s."
            )
            % request.user.email,
        )
        return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")

    response = HttpResponse(vcard, content_type="text/x-vCard;charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="vcard.vcf"'
    return response


def test():  # pragma: no cover
    from workbench.contacts.models import Person

    p = Person.objects.get(pk=2)

    print(person_to_vcard(p).serialize())
