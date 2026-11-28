import datetime as dt

from django.test import TestCase
from django.test.utils import override_settings
from django.utils import translation

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.contacts.merge import merge_people
from workbench.hosting.models import Server, Site, SiteContact
from workbench.invoices.models import RecurringInvoice
from workbench.tools.forms import WarningsForm


class SiteTest(TestCase):
    def setUp(self):
        self.enterContext(translation.override("en"))

    def test_problems(self):
        """Active sites need a running recurring invoice (or a reason why
        there's none) and an active contact for outages"""
        site = factories.SiteFactory.create()
        self.assertEqual(
            site.problems(), ["No recurring invoice", "No contact for outages"]
        )
        self.assertEqual(list(Site.objects.with_problems()), [site])

        person = factories.PersonFactory.create()
        SiteContact.objects.create(site=site, person=person, role=SiteContact.IT)
        self.assertIn("No contact for outages", site.problems())

        SiteContact.objects.create(site=site, person=person, role=SiteContact.OUTAGE)
        invoice = factories.RecurringInvoiceFactory.create(
            site=site, ends_on=dt.date.today() - dt.timedelta(days=1)
        )
        self.assertEqual(site.problems(), ["No recurring invoice"])

        invoice.ends_on = dt.date.today()
        invoice.save()
        self.assertEqual(site.problems(), [])
        self.assertEqual(list(Site.objects.with_problems()), [])

        # Archived contacts don't count
        person.is_archived = True
        person.save()
        self.assertEqual(site.problems(), ["No contact for outages"])
        self.assertEqual(
            Site.objects.with_problem_flags().get().problems(),
            ["No contact for outages"],
        )

        site.is_archived = True
        site.save()
        self.assertEqual(site.problems(), [])
        self.assertEqual(list(Site.objects.with_problems()), [])

    def test_no_invoice_reason(self):
        site = factories.SiteFactory.create(no_invoice_reason="Maintenance contract")
        self.assertEqual(site.problems(), ["No contact for outages"])

    def test_host_names(self):
        site = factories.SiteFactory.create(
            title="www.Example.com", domains="example.com\n\n  shop.example.com \n"
        )
        self.assertEqual(
            site.host_names(), ["www.example.com", "example.com", "shop.example.com"]
        )

    def test_search(self):
        site = factories.SiteFactory.create(
            title="www.example.com", domains="shop.example.org"
        )
        self.assertEqual(list(Site.objects.search("shop.example")), [site])
        self.assertEqual(list(Site.objects.search(site.customer.name)), [site])
        self.assertEqual(list(Site.objects.search(site.server.title)), [site])
        self.assertEqual(list(Site.objects.search("nothing")), [])

    def test_server_outage_contacts(self):
        """The outage contacts of the active sites, each person once"""
        site_a = factories.SiteFactory.create(title="a.example.com")
        site_b = factories.SiteFactory.create(
            title="b.example.com", server=site_a.server
        )
        archived = factories.SiteFactory.create(server=site_a.server, is_archived=True)
        person = factories.PersonFactory.create()
        it = factories.PersonFactory.create()
        for site in [site_a, site_b, archived]:
            SiteContact.objects.create(
                site=site, person=person, role=SiteContact.OUTAGE
            )
            SiteContact.objects.create(site=site, person=it, role=SiteContact.IT)
        SiteContact.objects.create(
            site=archived,
            person=factories.PersonFactory.create(),
            role=SiteContact.OUTAGE,
        )

        contacts = site_a.server.outage_contacts()
        self.assertEqual(contacts, [person])
        self.assertEqual(contacts[0].site_titles, [site_a, site_b])

    def test_merge_people(self):
        """Merging people moves their site contacts, without duplicates"""
        site = factories.SiteFactory.create()
        other = factories.SiteFactory.create()
        keep = factories.PersonFactory.create()
        duplicate = factories.PersonFactory.create(organization=keep.organization)
        SiteContact.objects.create(site=site, person=keep, role=SiteContact.OUTAGE)
        SiteContact.objects.create(site=site, person=duplicate, role=SiteContact.OUTAGE)
        SiteContact.objects.create(site=site, person=duplicate, role=SiteContact.IT)
        SiteContact.objects.create(
            site=other, person=duplicate, role=SiteContact.OUTAGE
        )

        merge_people(duplicate=duplicate, keep=keep)

        self.assertEqual(
            sorted(keep.site_contacts.values_list("site", "role")),
            sorted([
                (site.pk, SiteContact.OUTAGE),
                (site.pk, SiteContact.IT),
                (other.pk, SiteContact.OUTAGE),
            ]),
        )

    def test_delete_and_merge_site_contacts(self):
        """Deleting a person who is a site contact warns, merging them into
        someone of another organization names their sites (with HOSTING)"""
        site = factories.SiteFactory.create()
        person = factories.PersonFactory.create()
        SiteContact.objects.create(site=site, person=person, role=SiteContact.OUTAGE)
        SiteContact.objects.create(site=site, person=person, role=SiteContact.IT)
        keep = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)
        ajax = {"x-requested-with": "XMLHttpRequest"}

        response = self.client.post(person.urls["delete"])
        self.assertContains(response, "lose-contact")
        self.assertContains(response, "is the contact of 1 site")

        response = self.client.post(
            person.urls["merge"], {"modal-into": keep.pk}, headers=ajax
        )
        self.assertContains(response, "other-organization")
        self.assertContains(response, "1 site of")

        with override_settings(FEATURES={FEATURES.HOSTING: F.NEVER}):
            response = self.client.post(
                person.urls["merge"], {"modal-into": keep.pk}, headers=ajax
            )
            self.assertEqual(response.status_code, 299)

        response = self.client.post(
            keep.urls["delete"], {WarningsForm.ignore_warnings_id: "lose-contact"}
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SiteContact.objects.exists())

    def test_active_sites_keep_contacts(self):
        """Contacts of active sites and the customers of active sites aren't
        archived as unused"""
        from django.utils import timezone

        from workbench.contacts import tasks

        cutoff = timezone.now() + dt.timedelta(days=1)  # Every change is older
        site = factories.SiteFactory.create()
        person = factories.PersonFactory.create()
        SiteContact.objects.create(site=site, person=person, role=SiteContact.IT)
        self.assertNotIn(person, set(tasks.unused_people(cutoff)))
        self.assertNotIn(site.customer, set(tasks.unused_organizations(cutoff)))

        site.is_archived = True
        site.save()
        self.assertIn(person, set(tasks.unused_people(cutoff)))
        self.assertIn(site.customer, set(tasks.unused_organizations(cutoff)))


class ViewsTest(TestCase):
    def setUp(self):
        self.user = factories.UserFactory.create()
        self.client.force_login(self.user)

    def test_crud(self):
        """Servers, sites and their contacts are managed in the web interface"""
        response = self.client.post(Server.urls["create"], {"modal-title": "server01"})
        self.assertEqual(response.status_code, 302)
        server = Server.objects.get()

        organization = factories.OrganizationFactory.create()
        response = self.client.post(
            Site.urls["create"],
            {
                "title": " WWW.Example.com ",
                "domains": "Example.com\n\nshop.example.com",
                "server": server.pk,
                "customer": organization.pk,
                "owned_by": self.user.pk,
                "password_manager_url": "https://passwords.example.com/item/x",
            },
        )
        self.assertEqual(response.status_code, 302)
        site = Site.objects.get()
        self.assertEqual(site.title, "www.example.com")
        self.assertEqual(site.domains, "example.com\nshop.example.com")

        person = factories.PersonFactory.create(organization=organization)
        person.emailaddresses.create(email="hans@example.com")
        response = self.client.post(
            site.urls["add_contact"],
            {"modal-person": person.pk, "modal-role": SiteContact.OUTAGE},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 201)

        # Not twice with the same role
        response = self.client.post(
            site.urls["add_contact"],
            {"modal-person": person.pk, "modal-role": SiteContact.OUTAGE},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(
            response, "This person is already a contact of the site with this role."
        )

        response = self.client.get(site.urls["detail"])
        self.assertContains(response, "hans@example.com")
        self.assertContains(response, "No recurring invoice")
        self.assertContains(response, "https://passwords.example.com/item/x")

        response = self.client.get(server.urls["detail"])
        self.assertContains(response, "hans@example.com")

        response = self.client.get(Site.urls["list"] + "?s=problems")
        self.assertContains(response, "www.example.com")

        response = self.client.get(organization.urls["detail"])
        self.assertContains(response, site.urls["detail"])
        response = self.client.get(person.urls["detail"])
        self.assertContains(response, site.urls["detail"])

        contact = SiteContact.objects.get()
        response = self.client.post(
            contact.urls["delete"], headers={"x-requested-with": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(SiteContact.objects.count(), 0)

    def test_list_filters(self):
        site = factories.SiteFactory.create(title="a.example.com")
        other = factories.SiteFactory.create(title="b.example.com")
        archived = factories.SiteFactory.create(title="c.example.com", is_archived=True)
        for query, sites in [
            ("", [site, other]),
            (f"?server={site.server.pk}", [site]),
            (f"?org={other.customer.pk}", [other]),
            ("?q=b.example", [other]),
            ("?s=archived", [archived]),
            ("?s=all", [site, other, archived]),
        ]:
            with self.subTest(query=query):
                response = self.client.get(Site.urls["list"] + query)
                self.assertEqual(list(response.context["object_list"]), sites)

    def test_recurring_invoice_site(self):
        """Recurring invoices are created from their site and only offer the
        sites of their customer"""
        site = factories.SiteFactory.create()
        factories.SiteFactory.create()  # Another customer's
        response = self.client.get(RecurringInvoice.urls["create"] + f"?site={site.pk}")
        form = response.context["form"]
        self.assertEqual(form.initial["site"], site)
        self.assertEqual(form.initial["customer"], site.customer)
        self.assertEqual(list(form.fields["site"].queryset), [site])

        invoice = factories.RecurringInvoiceFactory.create(site=site)
        response = self.client.get(invoice.urls["detail"])
        self.assertContains(response, site.urls["detail"])

        response = self.client.get(site.urls["detail"])
        self.assertContains(response, invoice.urls["detail"])
        self.assertNotContains(response, "No recurring invoice")

    def test_recurring_invoice_other_customer(self):
        """Changing the customer of a recurring invoice needs another site"""
        from workbench.invoices.forms import RecurringInvoiceForm

        site = factories.SiteFactory.create()
        invoice = factories.RecurringInvoiceFactory.create(
            customer=site.customer, site=site, postal_address="Musterweg 1"
        )
        other = factories.OrganizationFactory.create()
        form = RecurringInvoiceForm(
            {
                "customer": other.pk,
                "title": invoice.title,
                "site": site.pk,
                "owned_by": self.user.pk,
                "postal_address": "Musterweg 1",
                "starts_on": invoice.starts_on.isoformat(),
                "periodicity": "yearly",
                "create_invoice_on_day": -20,
                "subtotal": 100,
                "third_party_costs": 0,
                "discount": 0,
                "new_invoices": RecurringInvoice.PREPARE,
            },
            instance=invoice,
            request=self.client.get("/").wsgi_request,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["site"], ["The site belongs to a different organization."]
        )

    def test_navigation(self):
        """Sites and servers belong to the contacts, each marked on its own"""
        for current, other in [
            (Site.urls["list"], Server.urls["list"]),
            (Server.urls["list"], Site.urls["list"]),
        ]:
            with self.subTest(url=current):
                response = self.client.get(current)
                self.assertContains(response, f'active" href="{current}"')
                self.assertNotContains(response, f'active" href="{other}"')
                self.assertContains(response, 'active" href="/contacts/"')

    def test_contact_phone_number(self):
        """Contacts of sites and servers show formatted phone numbers"""
        site = factories.SiteFactory.create()
        person = factories.PersonFactory.create()
        person.phonenumbers.create(phone_number="+41791234567", type="work")
        SiteContact.objects.create(site=site, person=person, role=SiteContact.OUTAGE)

        for url in [site.urls["detail"], site.server.urls["detail"]]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertContains(response, "+41 79 123 45 67")
                self.assertNotContains(response, ">+41791234567<")

    def test_duplicate_title(self):
        """Creating a site with the title of another site is a warning"""
        site = factories.SiteFactory.create(title="www.example.com")
        data = {
            "title": "WWW.example.com",
            "server": site.server.pk,
            "customer": site.customer.pk,
            "owned_by": self.user.pk,
        }
        response = self.client.post(Site.urls["create"], data)
        self.assertContains(response, "duplicate-site")
        self.assertContains(response, f"ID {site.pk}")

        response = self.client.post(
            Site.urls["create"],
            data | {WarningsForm.ignore_warnings_id: "duplicate-site"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Site.objects.filter(title="www.example.com").count(), 2)

    @override_settings(FEATURES={FEATURES.HOSTING: F.NEVER})
    def test_without_feature(self):
        site = factories.SiteFactory.create()
        for url in [Site.urls["list"], site.urls["detail"], site.server.urls["detail"]]:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, "/", fetch_redirect_response=False)

        response = self.client.get(site.customer.urls["detail"])
        self.assertNotContains(response, site.urls["detail"])
