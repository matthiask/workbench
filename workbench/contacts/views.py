from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
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


def person_vcard(request, pk):
    return VCardResponse(person_to_vcard(get_object_or_404(Person, pk=pk)).serialize())
