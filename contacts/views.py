from collections import OrderedDict

from django.contrib import messages
from django.db.models import ProtectedError
from django.http import HttpResponseRedirect
from django.utils.translation import ugettext as _

from contacts.forms import (
    PhoneNumberFormset, EmailAddressFormset, PostalAddressFormset)
from contacts.models import Organization, Person, PhoneNumber, EmailAddress, PostalAddress
from tools.deletion import related_classes
from tools.views import (
    ListView, DetailView, CreateView, UpdateView, DeleteView)


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


class OrganizationDeleteView(OrganizationViewMixin, DeleteView):
    def allow_delete(self, silent=False):
        try:
            if related_classes(self.object) <= {Organization}:
                return True
        except ProtectedError:
            pass

        if not silent:
            messages.error(
                self.request,
                _('Cannot delete "%s" because of related objects.')
                % self.object)

        return False


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

        kw = {'data': data, 'files': files}
        self.formsets = OrderedDict((
            ('phonenumbers', PhoneNumberFormset(**kw)),
            ('emailaddresses', EmailAddressFormset(**kw)),
            ('postaladdresses', PostalAddressFormset(**kw)),
        ))

        return form_class(data, files, **kwargs)


class PersonUpdateView(PersonViewMixin, UpdateView):
    def get_form(self, data=None, files=None, **kwargs):
        form_class = self.get_form_class()

        kw = {'data': data, 'files': files, 'instance': self.object}
        self.formsets = OrderedDict((
            ('phonenumbers', PhoneNumberFormset(**kw)),
            ('emailaddresses', EmailAddressFormset(**kw)),
            ('postaladdresses', PostalAddressFormset(**kw)),
        ))

        return form_class(data, files, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        for formset in self.formsets.values():
            formset.save()
        return response


class PersonDeleteView(PersonViewMixin, DeleteView):
    def allow_delete(self, silent=False):
        try:
            if related_classes(self.object) <= {
                Person,
                PhoneNumber,
                EmailAddress,
                PostalAddress,
            }:
                return True
        except ProtectedError:
            pass

        if not silent:
            messages.error(
                self.request,
                _('Cannot delete "%s" because of related objects.')
                % self.object)

        return False
