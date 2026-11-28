from django.test import TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.hosting.models import Server, Site, SiteContact


class HostingAPITest(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create()
        self.client.force_login(self.user)

    def test_servers(self):
        response = self.client.post(
            "/api/hosting/servers/",
            {"title": "server01", "notes": "Classic"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "server01")

        # Titles are unique
        response = self.client.post(
            "/api/hosting/servers/",
            {"title": "server01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.patch(
            "/api/hosting/servers/SERVER01/",
            {"is_archived": True},
            content_type="application/json",
        )
        self.assertTrue(response.json()["is_archived"])
        self.assertEqual(response.json()["notes"], "Classic")

        self.assertEqual(self.client.get("/api/hosting/servers/").json()["count"], 0)
        response = self.client.get("/api/hosting/servers/?include_archived=1")
        self.assertEqual(response.json()["count"], 1)

        response = self.client.get("/api/hosting/servers/unknown/")
        self.assertEqual(response.status_code, 404)

    def test_sites(self):
        server = factories.ServerFactory.create(title="cluster")
        organization = factories.OrganizationFactory.create()
        response = self.client.post(
            "/api/hosting/sites/",
            {
                "title": "WWW.Example.com",
                "domains": ["Example.com"],
                "server": "CLUSTER",
                "customer": organization.pk,
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(data["title"], "www.example.com")
        self.assertEqual(data["host_names"], ["www.example.com", "example.com"])
        self.assertEqual(data["server"], {"id": server.pk, "title": "cluster"})
        self.assertEqual(data["owned_by"], self.user.get_short_name())
        self.assertEqual(
            data["problems"], ["no_recurring_invoice", "no_outage_contact"]
        )
        self.assertEqual(data["recurring_invoices"], [])
        site = Site.objects.get()

        person = factories.PersonFactory.create(organization=organization)
        person.emailaddresses.create(email="hans@example.com")
        response = self.client.post(
            "/api/hosting/sites/www.example.com/contacts/",
            {"person": person.pk, "role": "outage"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        [contact] = response.json()["contacts"]
        self.assertEqual(contact["email"], "hans@example.com")
        self.assertEqual(contact["role"], "outage")
        self.assertEqual(response.json()["problems"], ["no_recurring_invoice"])

        response = self.client.post(
            f"/api/hosting/sites/{site.pk}/contacts/",
            {"person": person.pk, "role": "outage"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.get("/api/hosting/servers/cluster/")
        self.assertEqual(response.json()["sites"], ["www.example.com"])
        [outage] = response.json()["outage_contacts"]
        self.assertEqual(outage["email"], "hans@example.com")
        self.assertEqual(outage["sites"], ["www.example.com"])

        response = self.client.patch(
            f"/api/hosting/sites/{site.pk}/",
            {"no_invoice_reason": "Maintenance contract", "domains": []},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["problems"], [])
        self.assertEqual(response.json()["domains"], [])

        response = self.client.post(
            f"/api/hosting/sites/{site.pk}/contacts/remove/",
            {"person": person.pk},
            content_type="application/json",
        )
        self.assertEqual(response.json()["contacts"], [])
        response = self.client.post(
            f"/api/hosting/sites/{site.pk}/contacts/remove/",
            {"person": person.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.get("/api/hosting/sites/?problems=1&server=cluster")
        self.assertEqual(response.json()["count"], 1)

        response = self.client.patch(
            f"/api/hosting/sites/{site.pk}/",
            {"is_archived": True},
            content_type="application/json",
        )
        self.assertTrue(response.json()["is_archived"])
        self.assertEqual(self.client.get("/api/hosting/sites/").json()["count"], 0)
        response = self.client.get("/api/hosting/sites/?include_archived=1")
        self.assertEqual(response.json()["count"], 1)

    def test_duplicate_titles(self):
        """A title another site has already is a warning; titles find the
        active site first"""
        archived = factories.SiteFactory.create(
            title="www.example.com", is_archived=True
        )
        other = factories.SiteFactory.create(title="shop.example.com")

        def post(query=""):
            return self.client.post(
                f"/api/hosting/sites/{query}",
                {
                    "title": "WWW.example.com",
                    "server": archived.server.title,
                    "customer": archived.customer.pk,
                },
                content_type="application/json",
            )

        response = post()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            [error["code"] for error in response.json()["detail"]],
            ["duplicate-site"],
        )
        response = post("?ignore_warnings=duplicate-site")
        self.assertEqual(response.status_code, 200, response.content)
        site_id = response.json()["id"]

        response = self.client.get("/api/hosting/sites/www.example.com/")
        self.assertEqual(response.json()["id"], site_id)

        url = f"/api/hosting/sites/{other.pk}/"
        response = self.client.patch(
            url, {"title": "www.example.com"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)
        response = self.client.patch(
            url, {"notes": "Unchanged title"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)

    def test_unknown_references(self):
        organization = factories.OrganizationFactory.create()
        response = self.client.post(
            "/api/hosting/sites/",
            {"title": "example.com", "server": "nowhere", "customer": organization.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"][0]["loc"], ["body", "data", "server"]
        )
        response = self.client.get("/api/hosting/sites/?server=nowhere")
        self.assertEqual(response.status_code, 422)

    def test_recurring_invoice_site(self):
        site = factories.SiteFactory.create()
        invoice = factories.RecurringInvoiceFactory.create(
            customer=site.customer,
            postal_address="Beispiel AG\nMusterweg 1\n8000 Zürich",
        )
        response = self.client.patch(
            f"/api/recurring-invoices/{invoice.pk}/",
            {"site": site.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["site"], {"id": site.pk, "title": site.title})

        response = self.client.get(f"/api/recurring-invoices/?site={site.pk}")
        self.assertEqual(response.json()["count"], 1)

        response = self.client.get(f"/api/hosting/sites/{site.pk}/")
        self.assertEqual(response.json()["recurring_invoices"][0]["id"], invoice.pk)

        response = self.client.patch(
            f"/api/recurring-invoices/{invoice.pk}/",
            {"site": None},
            content_type="application/json",
        )
        self.assertIsNone(response.json()["site"])

    def test_site_delete(self):
        """Deleting a site like in the web interface: its contacts go with it,
        recurring invoices only lose their site"""
        site = factories.SiteFactory.create(title="www.example.com")
        site.contacts.create(person=factories.PersonFactory.create(), role="outage")
        invoice = factories.RecurringInvoiceFactory.create(
            customer=site.customer,
            postal_address="Beispiel AG\nMusterweg 1\n8000 Zürich",
            site=site,
        )

        response = self.client.delete("/api/hosting/sites/www.example.com/?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], site.pk)
        self.assertEqual(response.json()["recurring_invoices"][0]["id"], invoice.pk)
        self.assertTrue(Site.objects.filter(pk=site.pk).exists())

        response = self.client.delete(f"/api/hosting/sites/{site.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "www.example.com")
        self.assertFalse(Site.objects.filter(pk=site.pk).exists())
        self.assertFalse(SiteContact.objects.exists())
        invoice.refresh_from_db()
        self.assertIsNone(invoice.site)

        response = self.client.delete(f"/api/hosting/sites/{site.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_server_delete(self):
        """Servers with sites (also archived ones) can't be deleted, like in
        the web interface"""
        site = factories.SiteFactory.create(title="www.example.com", is_archived=True)
        server = site.server

        response = self.client.delete(f"/api/hosting/servers/{server.pk}/")
        self.assertEqual(response.status_code, 422)
        [error] = response.json()["detail"]
        self.assertEqual(error["loc"], ["path", "server_id"])
        self.assertIn("www.example.com", error["msg"])

        site.delete()
        response = self.client.delete(f"/api/hosting/servers/{server.title}/?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], server.pk)
        self.assertTrue(Server.objects.filter(pk=server.pk).exists())

        response = self.client.delete(f"/api/hosting/servers/{server.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], server.title)
        self.assertFalse(Server.objects.exists())

    def test_site_contact_update(self):
        """The role (and the person) of a site contact, through the form"""
        site = factories.SiteFactory.create(title="www.example.com")
        person = factories.PersonFactory.create()
        contact = site.contacts.create(person=person, role="outage")
        url = f"/api/hosting/sites/www.example.com/contacts/{contact.pk}/"

        response = self.client.patch(
            url + "?dry_run=1", {"role": "it"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["contacts"][0]["role"], "it")
        contact.refresh_from_db()
        self.assertEqual(contact.role, "outage")

        response = self.client.patch(
            url, {"role": "it"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        [data] = response.json()["contacts"]
        self.assertEqual(data["contact_id"], contact.pk)
        self.assertEqual(data["role"], "it")
        self.assertIn("no_outage_contact", response.json()["problems"])
        contact.refresh_from_db()
        self.assertEqual(contact.role, "it")

        # The form refuses duplicates
        site.contacts.create(person=person, role="outage")
        response = self.client.patch(
            url, {"role": "outage"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.patch(
            url, {"role": "boss"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)

        other = factories.PersonFactory.create()
        response = self.client.patch(
            url, {"person": other.pk}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200, response.content)
        contact.refresh_from_db()
        self.assertEqual(contact.person, other)

        # Only contacts of this site
        other_site = factories.SiteFactory.create(title="www.example.org")
        response = self.client.patch(
            f"/api/hosting/sites/{other_site.pk}/contacts/{contact.pk}/",
            {"role": "outage"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 404)

    @override_settings(FEATURES={FEATURES.HOSTING: F.NEVER})
    def test_without_feature(self):
        self.assertEqual(self.client.get("/api/hosting/sites/").status_code, 403)
        site = factories.SiteFactory.create()
        self.assertEqual(
            self.client.delete(f"/api/hosting/sites/{site.pk}/").status_code, 403
        )
        self.assertTrue(Site.objects.exists())

    def test_without_controlling(self):
        site = factories.SiteFactory.create()
        with override_settings(FEATURES={FEATURES.HOSTING: F.ALWAYS}):
            response = self.client.get(f"/api/hosting/sites/{site.pk}/")
        self.assertIsNone(response.json()["recurring_invoices"])
