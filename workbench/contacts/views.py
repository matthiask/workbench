from django.contrib import messages
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _

from workbench.contacts.forms import OrganizationSearchForm, PersonAutocompleteForm
from workbench.contacts.merge import (
    possible_duplicates,
    possible_organization_duplicates,
)
from workbench.contacts.models import Organization, Person
from workbench.generic import ListView
from workbench.tools.vcard import person_to_vcard, render_vcard_response


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
    person = get_object_or_404(Person, pk=pk)
    vcard = person_to_vcard(person).serialize()
    return render_vcard_response(request, vcard, subject=person.full_name)


def merge(request, pk, *, model, form_class):
    """Merge a duplicate into the contact to keep (``?into=`` preselects it)
    and go there (or to ``?next=``)"""
    instance = get_object_or_404(model, pk=pk)
    form = form_class(
        request.POST if request.method == "POST" else None,
        instance=instance,
        request=request,
        initial={"into": request.GET.get("into")},
    )
    if form.is_valid():
        keep = form.save()
        messages.success(
            request,
            _("%(duplicate)s has been merged into %(keep)s.")
            % {"duplicate": instance, "keep": keep},
        )
        url = request.GET.get("next")
        if not url_has_allowed_host_and_scheme(url, allowed_hosts=None):
            url = keep.get_absolute_url()
        if request.is_ajax():
            return JsonResponse({"redirect": url}, status=299)
        return redirect(url)
    return render(
        request,
        "modalform.html",
        {"form": form, "title": _("Merge %(instance)s") % {"instance": instance}},
    )


def duplicates(request):
    return render(
        request,
        "contacts/duplicates.html",
        {"groups": possible_duplicates()},
    )


def organization_duplicates(request):
    return render(
        request,
        "contacts/organization_duplicates.html",
        {"groups": possible_organization_duplicates()},
    )
