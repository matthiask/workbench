from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _

from workbench.contacts.forms import (
    OrganizationSearchForm,
    PersonAutocompleteForm,
    PersonSearchForm,
)
from workbench.contacts.models import Organization, Person
from workbench.generic import ListView


class OrganizationListView(ListView):
    model = Organization
    search_form_class = OrganizationSearchForm

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .prefetch_related(Prefetch("people", queryset=Person.objects.active()))
        )


class PersonListView(ListView):
    model = Person
    search_form_class = PersonSearchForm

    def get_queryset(self):
        queryset = super().get_queryset().active().select_related("organization")
        return queryset.extra(
            select={
                "email": (
                    "(SELECT email FROM contacts_emailaddress"
                    " WHERE contacts_emailaddress.person_id=contacts_person.id"
                    " ORDER BY weight DESC LIMIT 1)"
                ),
                "phone_number": (
                    "(SELECT phone_number FROM contacts_phonenumber"
                    " WHERE contacts_phonenumber.person_id=contacts_person.id"
                    " ORDER BY weight DESC LIMIT 1)"
                ),
            }
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
