import factory

from accounts.models import User
from contacts.models import Person


class UserFactory(factory.DjangoModelFactory):
    is_active = True
    email = 'whaa@example.com'

    class Meta:
        model = User


class PersonFactory(factory.DjangoModelFactory):
    full_name = 'Vorname Nachname'
    primary_contact = factory.SubFactory(UserFactory)

    class Meta:
        model = Person
