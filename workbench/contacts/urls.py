from django.shortcuts import redirect
from django.urls import path

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
    path("", lambda request: redirect("contacts_person_list"), name="contacts"),
    path(
        "organizations/",
        OrganizationListView.as_view(),
        name="contacts_organization_list",
    ),
    path(
        "organizations/autocomplete/",
        generic.AutocompleteView.as_view(
            model=Organization,
            queryset=Organization.objects.active(),
        ),
        name="contacts_organization_autocomplete",
    ),
    path(
        "organizations/<int:pk>/",
        generic.DetailView.as_view(model=Organization),
        name="contacts_organization_detail",
    ),
    path(
        "organizations/create/",
        generic.CreateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_create",
    ),
    path(
        "organizations/<int:pk>/update/",
        generic.UpdateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_update",
    ),
    path(
        "organizations/<int:pk>/delete/",
        generic.DeleteView.as_view(
            model=Organization, delete_form_class=OrganizationDeleteForm
        ),
        name="contacts_organization_delete",
    ),
    path(
        "people/",
        generic.ListView.as_view(model=Person, search_form_class=PersonSearchForm),
        name="contacts_person_list",
    ),
    path(
        "people/autocomplete/",
        generic.AutocompleteView.as_view(
            model=Person,
            queryset=Person.objects.active().select_related("organization"),
            filter=autocomplete_filter,
            label_from_instance=lambda person: person.name_with_organization,
        ),
        name="contacts_person_autocomplete",
    ),
    path("people/select/", select, name="contacts_person_select"),
    path(
        "people/<int:pk>/",
        generic.DetailView.as_view(model=Person),
        name="contacts_person_detail",
    ),
    path(
        "people/create/",
        generic.CreateAndUpdateView.as_view(model=Person, form_class=PersonForm),
        name="contacts_person_create",
    ),
    path(
        "people/<int:pk>/update/",
        generic.UpdateView.as_view(form_class=PersonForm, model=Person),
        name="contacts_person_update",
    ),
    path(
        "people/<int:pk>/delete/",
        generic.DeleteView.as_view(model=Person),
        name="contacts_person_delete",
    ),
    path("people/<int:pk>/vcard/", person_vcard, name="contacts_person_vcard"),
]
