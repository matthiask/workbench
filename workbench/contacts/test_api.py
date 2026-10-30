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

    def test_detail(self):
        """Organizations and people with their contact details"""
        person = factories.PersonFactory.create(
            given_name="Hans",
            family_name="Muster",
            organization=factories.OrganizationFactory.create(),
        )
        person.emailaddresses.create(type="work", email="hans@example.com")
        person.phonenumbers.create(phone_number="+41 44 123 45 67")
        self.client.force_login(factories.UserFactory.create())

        data = self.client.get(
            f"/api/contacts/organizations/{person.organization_id}/"
        ).json()
        self.assertEqual(data["name"], person.organization.name)
        self.assertEqual(
            data["people"],
            [{"id": person.pk, "full_name": "Hans Muster", "is_archived": False}],
        )

        data = self.client.get(f"/api/contacts/people/{person.pk}/").json()
        self.assertEqual(data["full_name"], "Hans Muster")
        self.assertEqual(data["organization"]["id"], person.organization_id)
        self.assertEqual(
            data["email_addresses"], [{"type": "work", "value": "hans@example.com"}]
        )
        self.assertEqual(data["phone_numbers"][0]["value"], "+41 44 123 45 67")
        self.assertEqual(data["url"], f"http://testserver{person.get_absolute_url()}")

        self.assertEqual(self.client.get("/api/contacts/people/0/").status_code, 404)
