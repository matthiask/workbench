import datetime as dt

from django.test import TestCase
from django.utils import timezone
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.contacts.models import Group, Organization, Person
from workbench.projects.models import Project


class ContactsAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_search(self):
        """Organizations and people can be searched"""
        organization = factories.OrganizationFactory.create(name="Beispiel")
        factories.OrganizationFactory.create(name="Beispiel alt", is_archived=True)
        person = factories.PersonFactory.create(
            given_name="Hans", family_name="Muster", organization=organization
        )
        self.client.force_login(factories.UserFactory.create())

        data = self.client.get("/api/contacts/organizations/?q=beispiel").json()[
            "items"
        ]
        self.assertEqual([o["id"] for o in data], [organization.pk])
        self.assertEqual(
            data[0]["url"], f"http://testserver{organization.get_absolute_url()}"
        )
        data = self.client.get(
            "/api/contacts/organizations/?q=beispiel&include_archived=true"
        ).json()["items"]
        self.assertEqual(len(data), 2)

        data = self.client.get("/api/contacts/people/?q=muster").json()["items"]
        self.assertEqual(data[0]["id"], person.pk)
        self.assertEqual(data[0]["full_name"], "Hans Muster")
        self.assertEqual(
            (data[0]["given_name"], data[0]["family_name"]), ("Hans", "Muster")
        )
        self.assertEqual(
            data[0]["url"], f"http://testserver{person.get_absolute_url()}"
        )
        self.assertEqual(data[0]["organization"]["name"], "Beispiel")
        self.assertEqual(
            data[0]["organization"]["url"],
            f"http://testserver{organization.get_absolute_url()}",
        )
        data = self.client.get(
            f"/api/contacts/people/?organization={organization.pk}"
        ).json()["items"]
        self.assertEqual([p["id"] for p in data], [person.pk])

    def test_people_filters(self):
        """People are filtered like in the web interface: by group (also
        through their organization), without any active group and by primary
        contact"""
        mailing = Group.objects.create(title="Mailing")
        industry = Group.objects.create(title="Industry", applies_to_organizations=True)
        old = Group.objects.create(title="Old", is_archived=True)
        organization = factories.OrganizationFactory.create()
        organization.groups.add(industry)
        member = factories.PersonFactory.create(given_name="Anna")
        member.groups.add(mailing)
        factories.PersonFactory.create(given_name="Bea", organization=organization)
        only_archived = factories.PersonFactory.create(given_name="Cleo")
        only_archived.groups.add(old)
        archived_member = factories.PersonFactory.create(
            given_name="Dora", is_archived=True
        )
        archived_member.groups.add(mailing)
        user = factories.UserFactory.create()
        self.client.force_login(user)

        def names(**params):
            response = self.client.get("/api/contacts/people/", params)
            self.assertEqual(response.status_code, 200, response.content)
            return [p["full_name"].split()[0] for p in response.json()["items"]]

        self.assertEqual(names(group="Mailing"), ["Anna"])
        self.assertEqual(
            names(group="mailing", include_archived="true"), ["Anna", "Dora"]
        )
        self.assertEqual(names(group=str(industry.pk)), ["Bea"])
        self.assertEqual(names(without_groups="true"), ["Cleo"])
        self.assertEqual(
            self.client.get("/api/contacts/people/", {"group": "Nope"}).status_code,
            422,
        )

        member.primary_contact = user
        member.save()
        self.assertEqual(names(primary_contact=user.get_short_name()), ["Anna"])

        data = self.client.get("/api/contacts/people/", {"group": "Mailing"}).json()
        self.assertEqual(data["items"][0]["groups"], ["Mailing"])
        self.assertEqual(data["items"][0]["primary_contact"], user.get_short_name())
        data = self.client.get("/api/contacts/people/", {"group": "Industry"}).json()
        self.assertEqual(data["items"][0]["groups"], ["Industry"])

    def test_people_postal_address(self):
        """The list has the postal address like the XLSX export: the one with
        the highest weight, e.g. work before home"""
        person = factories.PersonFactory.create()
        person.postaladdresses.create(
            type="home",
            street="Nebenweg",
            house_number="2",
            postal_code="3000",
            city="Bern",
        )
        person.postaladdresses.create(
            type="work",
            street="Hauptstrasse",
            house_number="1",
            postal_code="8000",
            city="Zürich",
            country="CH",
            postal_address_override="Override",
        )
        other = factories.PersonFactory.create()
        self.client.force_login(factories.UserFactory.create())
        items = {
            p["id"]: p for p in self.client.get("/api/contacts/people/").json()["items"]
        }
        address = items[person.pk]["postal_address"]
        self.assertEqual(
            (address["street"], address["city"], address["country"]),
            ("Hauptstrasse", "Zürich", "CH"),
        )
        self.assertEqual(address["postal_address_override"], "Override")
        self.assertIsNone(items[other.pk]["postal_address"])

    def test_people_with_recent_projects_or_deals(self):
        """People who are the contact of projects or deals created since a
        date, like the defined search of the web interface"""
        project = factories.ProjectFactory.create()
        deal = factories.DealFactory.create(contact=factories.PersonFactory.create())
        old = factories.ProjectFactory.create()
        Project.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - dt.timedelta(days=1000)
        )
        factories.PersonFactory.create()
        self.client.force_login(factories.UserFactory.create())

        def ids(since):
            response = self.client.get(
                "/api/contacts/people/", {"projects_or_deals_since": since}
            )
            self.assertEqual(response.status_code, 200, response.content)
            return {p["id"] for p in response.json()["items"]}

        recent = dt.date.today() - dt.timedelta(days=365)
        self.assertEqual(ids(recent), {project.contact_id, deal.contact_id})
        self.assertEqual(
            ids(recent - dt.timedelta(days=1000)),
            {project.contact_id, deal.contact_id, old.contact_id},
        )

    def test_update_person(self):
        """People get a primary contact, are added to and removed from groups
        with the rules of the person form (groups which apply to organizations
        go to the organization) and archived"""
        mailing = Group.objects.create(title="Mailing")
        industry = Group.objects.create(title="Industry", applies_to_organizations=True)
        old = Group.objects.create(title="Old", is_archived=True)
        organization = factories.OrganizationFactory.create()
        person = factories.PersonFactory.create(organization=organization)
        user = factories.UserFactory.create(_short_name="xy")
        self.client.force_login(user)
        url = f"/api/contacts/people/{person.pk}/"

        def patch(data, query=""):
            return self.client.patch(
                f"{url}{query}", data, content_type="application/json"
            )

        response = patch(
            {"primary_contact": "XY", "add_groups": ["Mailing", str(industry.pk)]},
            "?dry_run=true",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["groups"], ["Industry", "Mailing"])
        self.assertEqual(list(person.groups.all()), [])

        response = patch({
            "primary_contact": "XY",
            "add_groups": ["Mailing", str(industry.pk)],
        })
        self.assertEqual(response.json()["primary_contact"], "xy")
        self.assertEqual(list(person.groups.all()), [mailing])
        self.assertEqual(list(organization.groups.all()), [industry])

        response = patch({"remove_groups": ["Mailing", "Industry"]})
        self.assertEqual(response.json()["groups"], [])
        self.assertEqual(list(organization.groups.all()), [])

        for data, loc in [
            ({"add_groups": ["Old"]}, ["body", "data", "add_groups", 0]),
            ({"add_groups": ["Nope"]}, ["body", "data", "add_groups", 0]),
            ({"primary_contact": "nobody"}, ["body", "data", "primary_contact"]),
        ]:
            response = patch(data)
            self.assertEqual(response.status_code, 422, data)
            self.assertEqual([e["loc"] for e in response.json()["detail"]], [loc])

        # Archived groups can be removed if the person is in them
        person.groups.add(old)
        response = patch({"remove_groups": ["Old"], "is_archived": True})
        self.assertEqual(response.status_code, 200, response.content)
        person.refresh_from_db()
        self.assertTrue(person.is_archived)
        self.assertEqual(list(person.groups.all()), [])

    def test_groups(self):
        """Groups are listed with their members, created and changed with the
        form of the web interface; titles are unique"""
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        mailing = Group.objects.create(title="Mailing")
        person.groups.add(mailing)
        Group.objects.create(title="Old", is_archived=True)
        self.client.force_login(factories.UserFactory.create())

        data = self.client.get("/api/contacts/groups/").json()
        self.assertEqual(
            [(g["title"], g["people_count"]) for g in data["items"]], [("Mailing", 1)]
        )
        data = self.client.get("/api/contacts/groups/", {"s": "all"}).json()
        self.assertEqual([g["title"] for g in data["items"]], ["Mailing", "Old"])

        def send(method, path, data, query=""):
            return getattr(self.client, method)(
                f"/api/contacts/groups/{path}{query}",
                data,
                content_type="application/json",
            )

        response = send("post", "", {"title": "Christmas"}, "?dry_run=true")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Group.objects.filter(title="Christmas").exists())
        response = send("post", "", {"title": "Christmas"})
        christmas = Group.objects.get(title="Christmas")
        self.assertEqual(response.json()["id"], christmas.pk)

        response = send("post", "", {"title": "christmas"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"] for e in response.json()["detail"]], [["body", "data", "title"]]
        )

        # Like the form: groups which start to apply to organizations move
        # their people's memberships to the organizations
        response = send("patch", f"{mailing.pk}/", {"applies_to_organizations": True})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(person.organization.groups.all()), [mailing])
        response = send("patch", f"{mailing.pk}/", {"is_archived": True})
        self.assertTrue(response.json()["is_archived"])
        response = send("patch", f"{mailing.pk}/", {"title": "Christmas"})
        self.assertEqual(response.status_code, 422)

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
            [
                {
                    "id": person.pk,
                    "url": f"http://testserver{person.get_absolute_url()}",
                    "full_name": "Hans Muster",
                    "is_archived": False,
                }
            ],
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
            "new_organization": "Beispiel AG",
            "email_addresses": [
                {"email": "hans@example.com"},
                {"type": "private", "email": "hans@example.org"},
            ],
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
        self.assertEqual(data["organization"]["name"], "Beispiel AG")
        self.assertEqual(data["phone_numbers"][0]["value"], "+41791234567")
        self.assertFalse(Person.objects.exists())
        self.assertFalse(Organization.objects.exists())

        response = self.client.post(
            "/api/contacts/people/", person, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        created = Person.objects.get()
        self.assertEqual(created.organization.name, "Beispiel AG")
        self.assertEqual(created.organization.primary_contact, user)
        self.assertEqual(created.primary_contact, user)
        self.assertEqual(
            [(e.type, e.email) for e in created.emailaddresses.all()],
            [("work", "hans@example.com"), ("private", "hans@example.org")],
        )
        self.assertIn("Bahnhofstrasse 1", created.postaladdresses.get().postal_address)
        # The details are searchable
        self.assertIn("hans@example.com", created._fts)

        # Duplicates
        response = self.client.post(
            "/api/contacts/people/", person, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"][2:] for e in response.json()["detail"]],
            [
                ["email_addresses", 0, "email"],
                ["email_addresses", 1, "email"],
                [],
                ["new_organization"],
            ],
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
                "new_organization": "Beispiel AG",
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

    def test_add_details(self):
        """Details are added to existing people, never changed or removed"""
        person = factories.PersonFactory.create()
        person.phonenumbers.create(phone_number="+41791234567")
        person.emailaddresses.create(email="hans@example.com")
        self.client.force_login(factories.UserFactory.create())
        url = f"/api/contacts/people/{person.pk}/details/"

        response = self.client.post(
            url,
            {
                "email_addresses": [{"email": "HANS@example.com"}],
                "phone_numbers": [{"phone_number": "079 123 45 67"}],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [e["loc"][2:] for e in response.json()["detail"]],
            [["email_addresses", 0, "email"], ["phone_numbers", 0, "phone_number"]],
        )

        details = {
            "phone_numbers": [{"type": "work", "phone_number": "044 123 45 67"}],
            "postal_addresses": [
                {"street": "Bahnhofstrasse", "postal_code": "8001", "city": "Zürich"}
            ],
        }
        response = self.client.post(
            f"{url}?dry_run=true", details, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(response.json()["phone_numbers"]), 2)
        self.assertEqual(person.phonenumbers.count(), 1)

        response = self.client.post(url, details, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(person.phonenumbers.count(), 2)
        self.assertEqual(person.postaladdresses.count(), 1)
        person.refresh_from_db()
        self.assertIn("+41441234567", person._fts)
