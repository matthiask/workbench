from django.shortcuts import redirect
from django.urls import re_path

from workbench import generic
from workbench.contacts.forms import (
    OrganizationDeleteForm,
    OrganizationForm,
    PersonForm,
    PersonSearchForm,
)
from workbench.contacts.models import Organization, Person
from workbench.contacts.views import OrganizationListView, person_vcard, select


def autocomplete_filter(*, request, queryset):
    return (
        queryset.filter(organization__isnull=False)
        if request.GET.get("only_employees")
        else queryset
    )


urlpatterns = [
    re_path(r"^$", lambda request: redirect("contacts_person_list"), name="contacts"),
    re_path(
        r"^organizations/$",
        OrganizationListView.as_view(),
        name="contacts_organization_list",
    ),
    re_path(
        r"^organizations/autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Organization,
            queryset=Organization.objects.active(),
        ),
        name="contacts_organization_autocomplete",
    ),
    re_path(
        r"^organizations/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Organization),
        name="contacts_organization_detail",
    ),
    re_path(
        r"^organizations/create/$",
        generic.CreateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_create",
    ),
    re_path(
        r"^organizations/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_update",
    ),
    re_path(
        r"^organizations/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(
            model=Organization, delete_form_class=OrganizationDeleteForm
        ),
        name="contacts_organization_delete",
    ),
    re_path(
        r"^people/$",
        generic.ListView.as_view(model=Person, search_form_class=PersonSearchForm),
        name="contacts_person_list",
    ),
    re_path(
        r"^people/autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Person,
            queryset=Person.objects.active().select_related("organization"),
            filter=autocomplete_filter,
            label_from_instance=lambda person: person.name_with_organization,
        ),
        name="contacts_person_autocomplete",
    ),
    re_path(r"^people/select/$", select, name="contacts_person_select"),
    re_path(
        r"^people/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Person),
        name="contacts_person_detail",
    ),
    re_path(
        r"^people/create/$",
        generic.CreateAndUpdateView.as_view(model=Person, form_class=PersonForm),
        name="contacts_person_create",
    ),
    re_path(
        r"^people/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=PersonForm, model=Person),
        name="contacts_person_update",
    ),
    re_path(
        r"^people/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Person),
        name="contacts_person_delete",
    ),
    re_path(r"^people/(?P<pk>\d+)/vcard/$", person_vcard, name="contacts_person_vcard"),
]
