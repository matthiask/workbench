from datetime import date

import factory

from accounts.models import User
from contacts.models import Person


class UserFactory(factory.DjangoModelFactory):
    is_active = True
    email = 'whaa@example.com'
    date_of_birth = date(1980, 1, 15)

    class Meta:
        model = User


class PersonFactory(factory.DjangoModelFactory):
    full_name = 'Vorname Nachname'
    primary_contact = factory.SubFactory(UserFactory)

    class Meta:
        model = Person
