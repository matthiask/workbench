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
    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'primary_contact': self.request.user.pk,
        })
        form_class = self.get_form_class()
        return form_class(data, files, **kwargs)


class OrganizationUpdateView(OrganizationViewMixin, UpdateView):
    pass


class PersonListView(PersonViewMixin, ListView):
    def get_queryset(self):
        return super().get_queryset().select_related('organization')


class PersonDetailView(PersonViewMixin, DetailView):
    pass


class PersonCreateView(PersonViewMixin, CreateView):
    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'primary_contact': self.request.user.pk,
        })
        form_class = self.get_form_class()
        return form_class(data, files, **kwargs)


class PersonUpdateView(PersonViewMixin, UpdateView):
    pass
