from django.test import TestCase

from workbench import factories


class ContactsTestCase(TestCase):
    def test_stuff(self):
        factories.PersonFactory.create()
