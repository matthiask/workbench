import re

from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from workbench.contacts.forms import OrganizationSearchForm, PersonAutocompleteForm
from workbench.contacts.models import Organization, Person
from workbench.generic import ListView
from workbench.tools.vcard import VCardResponse, person_to_vcard


class OrganizationListView(ListView):
    model = Organization
    search_form_class = OrganizationSearchForm

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(Prefetch("people", queryset=Person.objects.active()))
        )


def select(request):
    form = PersonAutocompleteForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        return JsonResponse(
            {"redirect": form.cleaned_data["person"].get_absolute_url()}, status=299
        )
    return render(
        request,
        "generic/select_object.html",
        {"form": form, "title": _("Jump to person")},
    )


def is_ios(user_agent):
    return re.search(r"(ios|ipad|iphone)", user_agent, re.I)


def person_vcard(request, pk):
    person = get_object_or_404(Person, pk=pk)
    vcard = person_to_vcard(person).serialize()

    if is_ios(request.META.get("HTTP_USER_AGENT") or ""):
        mail = EmailMultiAlternatives(
            "vCard: {}".format(person.full_name), "", to=[request.user.email]
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
        return redirect(person)

    return VCardResponse(vcard)
