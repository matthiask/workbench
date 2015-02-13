# from contacts.forms import (
#     PhoneNumberFormset, EmailAddressFormset, PostalAddressFormset)
from contacts.models import Organization, Person
from tools.views import ListView, DetailView, CreateView, UpdateView


class OrganizationViewMixin(object):
    model = Organization


class PersonViewMixin(object):
    model = Person


class OrganizationListView(OrganizationViewMixin, ListView):
    pass


class OrganizationDetailView(OrganizationViewMixin, DetailView):
    pass


class OrganizationCreateView(OrganizationViewMixin, CreateView):
    pass


class OrganizationUpdateView(OrganizationViewMixin, UpdateView):
    pass


class PersonListView(PersonViewMixin, ListView):
    pass


class PersonDetailView(PersonViewMixin, DetailView):
    pass


class PersonCreateView(PersonViewMixin, CreateView):
    pass


class PersonUpdateView(PersonViewMixin, UpdateView):
    pass
