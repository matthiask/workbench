from django.conf.urls import url
from django.shortcuts import redirect

from workbench import generic
from workbench.contacts.forms import OrganizationForm, PersonForm
from workbench.contacts.models import Organization, Person
from workbench.contacts.views import OrganizationListView, PersonListView


urlpatterns = [
    url(r"^$", lambda request: redirect("contacts_person_list"), name="contacts"),
    url(
        r"^organizations/$",
        OrganizationListView.as_view(),
        name="contacts_organization_list",
    ),
    url(
        r"^organizations/autocomplete/$",
        generic.AutocompleteView.as_view(model=Organization),
        name="contacts_organization_autocomplete",
    ),
    url(
        r"^organizations/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Organization),
        name="contacts_organization_detail",
    ),
    url(
        r"^organizations/create/$",
        generic.CreateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_create",
    ),
    url(
        r"^organizations/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_update",
    ),
    url(
        r"^organizations/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Organization),
        name="contacts_organization_delete",
    ),
    url(r"^people/$", PersonListView.as_view(), name="contacts_person_list"),
    url(
        r"^people/autocomplete/$",
        generic.AutocompleteView.as_view(
            model=Person, queryset=Person.objects.select_related("organization")
        ),
        name="contacts_person_autocomplete",
    ),
    url(
        r"^people/(?P<pk>\d+)/$",
        generic.DetailView.as_view(model=Person),
        name="contacts_person_detail",
    ),
    url(
        r"^people/create/$",
        generic.CreateAndUpdateView.as_view(model=Person, form_class=PersonForm),
        name="contacts_person_create",
    ),
    url(
        r"^people/(?P<pk>\d+)/update/$",
        generic.UpdateView.as_view(form_class=PersonForm, model=Person),
        name="contacts_person_update",
    ),
    url(
        r"^people/(?P<pk>\d+)/delete/$",
        generic.DeleteView.as_view(model=Person),
        name="contacts_person_delete",
    ),
]
