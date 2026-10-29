from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories


class ContactsAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_search(self):
        """Organizations and people can be searched"""
        organization = factories.OrganizationFactory.create(name="Espoir")
        factories.OrganizationFactory.create(name="Espoir alt", is_archived=True)
        person = factories.PersonFactory.create(
            given_name="Hans", family_name="Muster", organization=organization
        )
        self.client.force_login(factories.UserFactory.create())

        data = self.client.get("/api/contacts/organizations/?q=espoir").json()
        self.assertEqual([o["id"] for o in data], [organization.pk])
        data = self.client.get(
            "/api/contacts/organizations/?q=espoir&include_archived=true"
        ).json()
        self.assertEqual(len(data), 2)

        data = self.client.get("/api/contacts/people/?q=muster").json()
        self.assertEqual(data[0]["id"], person.pk)
        self.assertEqual(data[0]["full_name"], "Hans Muster")
        self.assertEqual(data[0]["organization"]["name"], "Espoir")
        data = self.client.get(
            f"/api/contacts/people/?organization={organization.pk}"
        ).json()
        self.assertEqual([p["id"] for p in data], [person.pk])
