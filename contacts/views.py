from collections import OrderedDict

from django.shortcuts import redirect

from contacts.forms import (
    OrganizationSearchForm, PersonForm, PhoneNumberFormset,
    EmailAddressFormset, PostalAddressFormset)
from contacts.models import Person
from tools.views import ListView, UpdateView


class PersonListView(ListView):
    model = Person
    search_form_class = OrganizationSearchForm

    def get_queryset(self):
        return super().get_queryset().select_related(
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


class PersonUpdateView(UpdateView):
    form_class = PersonForm
    model = Person

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
