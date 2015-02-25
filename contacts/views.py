from collections import OrderedDict

from django.shortcuts import redirect

from contacts.forms import (
    OrganizationSearchForm, OrganizationForm, PersonForm, PhoneNumberFormset,
    EmailAddressFormset, PostalAddressFormset)
from contacts.models import (
    Organization, Person, PhoneNumber, EmailAddress, PostalAddress)
from tools.views import (
    ListView, DetailView, CreateView, UpdateView, DeleteView)


class OrganizationViewMixin(object):
    model = Organization
    allow_delete_if_only = {Organization}


class PersonViewMixin(object):
    model = Person
    allow_delete_if_only = {
        Person, PhoneNumber, EmailAddress, PostalAddress}


class OrganizationListView(OrganizationViewMixin, ListView):
    def get_queryset(self):
        queryset = super().get_queryset()

        self.search_form = OrganizationSearchForm(self.request.GET)
        if self.search_form.is_valid():
            data = self.search_form.cleaned_data
            if data.get('g'):
                queryset = queryset.filter(groups=data.get('g'))

        return queryset


class OrganizationPickerView(OrganizationListView):
    template_name_suffix = '_picker'


class OrganizationDetailView(OrganizationViewMixin, DetailView):
    pass


class OrganizationCreateView(OrganizationViewMixin, CreateView):
    form_class = OrganizationForm

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'primary_contact': self.request.user.pk,
        })
        form_class = self.get_form_class()
        return form_class(data, files, **kwargs)


class OrganizationUpdateView(OrganizationViewMixin, UpdateView):
    form_class = OrganizationForm


class OrganizationDeleteView(OrganizationViewMixin, DeleteView):
    pass


class PersonListView(PersonViewMixin, ListView):
    def get_queryset(self):
        queryset = super().get_queryset()

        self.search_form = OrganizationSearchForm(self.request.GET)
        if self.search_form.is_valid():
            data = self.search_form.cleaned_data
            if data.get('g'):
                queryset = queryset.filter(groups=data.get('g'))

        return queryset.select_related(
            'organization',
        ).extra(select={
            'email': (
                '(SELECT email FROM contacts_emailaddress'
                ' WHERE contacts_emailaddress.person_id=contacts_person.id'
                ' ORDER BY weight DESC LIMIT 1)'
            ),
            'phone_number': (
                '(SELECT phone_number FROM contacts_phonenumber'
                ' WHERE contacts_phonenumber.person_id=contacts_person.id'
                ' ORDER BY weight DESC LIMIT 1)'
            ),
        })


class PersonPickerView(PersonListView):
    template_name_suffix = '_picker'


class PersonDetailView(PersonViewMixin, DetailView):
    pass


class PersonCreateView(PersonViewMixin, CreateView):
    form_class = PersonForm

    def get_form(self, data=None, files=None, **kwargs):
        kwargs.setdefault('initial', {}).update({
            'primary_contact': self.request.user.pk,
        })
        form_class = self.get_form_class()
        return form_class(data, files, **kwargs)


class PersonUpdateView(PersonViewMixin, UpdateView):
    form_class = PersonForm

    def get_form(self, data=None, files=None, **kwargs):
        form_class = self.get_form_class()

        kw = {'data': data, 'files': files, 'instance': self.object}
        self.formsets = OrderedDict((
            ('phonenumbers', PhoneNumberFormset(**kw)),
            ('emailaddresses', EmailAddressFormset(**kw)),
            ('postaladdresses', PostalAddressFormset(**kw)),
        ))

        return form_class(data, files, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if not self.allow_update():
            return redirect(self.object)

        form = self.get_form(
            data=request.POST, files=request.FILES, instance=self.object)
        if form.is_valid() and all(
                f.is_valid() for f in self.formsets.values()):
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        for formset in self.formsets.values():
            formset.save()
        return response


class PersonDeleteView(PersonViewMixin, DeleteView):
    pass
