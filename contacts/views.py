from contacts.forms import (
    PhoneNumberFormset, EmailAddressFormset, PostalAddressFormset)
from contacts.models import Organization, Person
from tools.views import ListView, DetailView


class OrganizationViewMixin(object):
    model = Organization


class PersonViewMixin(object):
    model = Person


class OrganizationListView(OrganizationViewMixin, ListView):
    pass


class OrganizationDetailView(OrganizationViewMixin, DetailView):
    pass


class PersonListView(PersonViewMixin, ListView):
    pass


class PersonDetailView(PersonViewMixin, DetailView):
    pass
