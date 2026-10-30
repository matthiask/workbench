from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.contacts.models import Organization, Person


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

    def test_create(self):
        """People are created with their details and their organization"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        person = {
            "given_name": "Hans",
            "family_name": "Muster",
            "address": "Herr",
            "salutation": "Lieber Hans",
            "new_organization": "Espoir AG",
            "email_addresses": [{"email": "hans@espoir.ch"}],
            "phone_numbers": [{"type": "mobile", "phone_number": "079 123 45 67"}],
            "postal_addresses": [
                {
                    "street": "Bahnhofstrasse",
                    "house_number": "1",
                    "postal_code": "8001",
                    "city": "Zürich",
                }
            ],
        }
        response = self.client.post(
            "/api/contacts/people/?dry_run=true",
            person,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["id"], None)
        self.assertEqual(data["organization"]["name"], "Espoir AG")
        self.assertEqual(data["phone_numbers"][0]["value"], "+41791234567")
        self.assertFalse(Person.objects.exists())
        self.assertFalse(Organization.objects.exists())

        response = self.client.post(
            "/api/contacts/people/", person, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        created = Person.objects.get()
        self.assertEqual(created.organization.name, "Espoir AG")
        self.assertEqual(created.organization.primary_contact, user)
        self.assertEqual(created.primary_contact, user)
        self.assertEqual(created.emailaddresses.get().email, "hans@espoir.ch")
        self.assertIn("Bahnhofstrasse 1", created.postaladdresses.get().postal_address)
        # The details are searchable
        self.assertIn("hans@espoir.ch", created._fts)

        # Duplicates
        response = self.client.post(
            "/api/contacts/people/", person, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"][2:] for e in response.json()["detail"]],
            [["email_addresses", 0, "email"], [], ["new_organization"]],
        )
        person["email_addresses"] = []
        person["new_organization"] = None
        person["organization"] = created.organization_id
        response = self.client.post(
            "/api/contacts/people/?allow_duplicates=true",
            person,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Person.objects.count(), 2)
        self.assertEqual(Organization.objects.count(), 1)

    def test_create_errors(self):
        """Nothing is saved if anything is invalid"""
        self.client.force_login(factories.UserFactory.create())
        response = self.client.post(
            "/api/contacts/people/",
            {
                "given_name": "Hans",
                "family_name": "Muster",
                "salutation": "Hans",
                "new_organization": "Espoir AG",
                "email_addresses": [{"email": "nope"}],
                "phone_numbers": [{"phone_number": "123"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"][2:] for e in response.json()["detail"]],
            [
                ["email_addresses", 0, "email"],
                ["phone_numbers", 0, "phone_number"],
                [],  # Short salutation
            ],
        )
        self.assertFalse(Organization.objects.exists())

    def test_context(self):
        """The schema of people to create"""
        self.client.force_login(factories.UserFactory.create())
        data = self.client.get("/api/contacts/people/context/").json()
        self.assertIn("salutation", data["import_schema"]["properties"])
