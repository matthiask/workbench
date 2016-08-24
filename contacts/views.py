from contacts.forms import OrganizationSearchForm, PersonForm
from contacts.models import Organization, Person
from tools.views import ListView, CreateView


class OrganizationListView(ListView):
    model = Organization
    search_form_class = OrganizationSearchForm

    def get_queryset(self):
        return super().get_queryset().prefetch_related('people')


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


class PersonCreateView(CreateView):
    form_class = PersonForm
    model = Person

    def get_success_url(self):
        return self.object.urls.url('update')
