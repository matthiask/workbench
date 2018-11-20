from django.conf.urls import url
from django.shortcuts import redirect

from workbench.contacts.forms import OrganizationForm, PersonForm
from workbench.contacts.models import Organization, Person
from workbench.contacts.views import OrganizationListView, PersonListView, PersonCreateView
from workbench.tools.views import ListView, DetailView, CreateView, UpdateView, DeleteView


urlpatterns = [
    url(r"^$", lambda request: redirect("contacts_organization_list"), name="contacts"),
    url(
        r"^organizations/$",
        OrganizationListView.as_view(),
        name="contacts_organization_list",
    ),
    url(
        r"^organizations/picker/$",
        ListView.as_view(
            model=Organization, template_name_suffix="_picker", paginate_by=10
        ),
        name="contacts_organization_picker",
    ),
    url(
        r"^organizations/(?P<pk>\d+)/$",
        DetailView.as_view(model=Organization),
        name="contacts_organization_detail",
    ),
    url(
        r"^organizations/create/$",
        CreateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_create",
    ),
    url(
        r"^organizations/(?P<pk>\d+)/update/$",
        UpdateView.as_view(form_class=OrganizationForm, model=Organization),
        name="contacts_organization_update",
    ),
    url(
        r"^organizations/(?P<pk>\d+)/delete/$",
        DeleteView.as_view(model=Organization),
        name="contacts_organization_delete",
    ),
    url(r"^people/$", PersonListView.as_view(), name="contacts_person_list"),
    url(
        r"^people/picker/$",
        PersonListView.as_view(template_name_suffix="_picker", paginate_by=10),
        name="contacts_person_picker",
    ),
    url(
        r"^people/(?P<pk>\d+)/$",
        DetailView.as_view(model=Person),
        name="contacts_person_detail",
    ),
    url(r"^people/create/$", PersonCreateView.as_view(), name="contacts_person_create"),
    url(
        r"^people/(?P<pk>\d+)/update/$",
        UpdateView.as_view(form_class=PersonForm, model=Person),
        name="contacts_person_update",
    ),
    url(
        r"^people/(?P<pk>\d+)/delete/$",
        DeleteView.as_view(model=Person),
        name="contacts_person_delete",
    ),
]
