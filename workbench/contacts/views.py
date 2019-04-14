from workbench.contacts.forms import OrganizationSearchForm, PersonSearchForm
from workbench.contacts.models import Organization, Person
from workbench.generic import ListView


class OrganizationListView(ListView):
    model = Organization
    search_form_class = OrganizationSearchForm

    def get_queryset(self):
        return super().get_queryset().prefetch_related("people")


class PersonListView(ListView):
    model = Person
    search_form_class = PersonSearchForm

    def get_root_queryset(self):
        return Person.objects.active()

    def get_queryset(self):
        queryset = super().get_queryset().select_related("organization")
        return queryset.extra(
            select={
                "email": (
                    "(SELECT email FROM contacts_emailaddress"
                    " WHERE contacts_emailaddress.person_id=contacts_person.id"
                    " ORDER BY weight DESC LIMIT 1)"
                ),
                "phone_number": (
                    "(SELECT phone_number FROM contacts_phonenumber"
                    " WHERE contacts_phonenumber.person_id=contacts_person.id"
                    " ORDER BY weight DESC LIMIT 1)"
                ),
            }
        )
