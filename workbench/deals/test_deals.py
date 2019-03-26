from datetime import date

from django.test import TestCase

from workbench import factories
from workbench.tools.formats import local_date_format


class DealsTest(TestCase):
    def test_list(self):
        self.client.force_login(factories.UserFactory.create())

        self.assertEqual(self.client.get("/deals/").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=all").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=10").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=20").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=30").status_code, 200)
        self.assertEqual(self.client.get("/deals/?s=40").status_code, 302)

    def test_detail(self):
        deal = factories.DealFactory.create()

        self.client.force_login(deal.owned_by)
        response = self.client.get(deal.urls["detail"])
        # print(response, response.content.decode("utf-8"))

        self.assertContains(response, "Keine Aktivitäten")
        self.assertContains(response, "<td>42.00</td>")

    def test_crud(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create()
        )
        self.client.force_login(person.primary_contact)

        response = self.client.post(
            "/deals/create/",
            {
                "customer": person.organization.id,
                "contact": person.id,
                "title": "Some deal",
                "stage": factories.StageFactory.create().pk,
                "owned_by": person.primary_contact_id,
                "estimated_value": 5000,
                "status": factories.Deal.OPEN,
            },
        )
        self.assertEqual(response.status_code, 302)
        deal = factories.Deal.objects.get()
        self.assertIsNone(deal.closed_on)
        self.assertEqual(
            deal.pretty_status, "Offen seit {}".format(local_date_format(date.today()))
        )

        response = self.client.post(
            deal.urls["update"],
            {
                "customer": person.organization.id,
                "contact": person.id,
                "title": "Some deal",
                "stage": factories.StageFactory.create().pk,
                "owned_by": person.primary_contact_id,
                "estimated_value": 5000,
                "status": factories.Deal.DECLINED,
            },
        )

        deal.refresh_from_db()
        self.assertEqual(deal.closed_on, date.today())
        self.assertEqual(
            deal.pretty_status,
            "Abgelehnt am {}".format(local_date_format(date.today())),
        )

        response = self.client.post(
            deal.urls["update"],
            {
                "customer": person.organization.id,
                "contact": person.id,
                "title": "Some deal",
                "stage": factories.StageFactory.create().pk,
                "owned_by": person.primary_contact_id,
                "estimated_value": 5000,
                "status": factories.Deal.OPEN,
            },
        )

        deal.refresh_from_db()
        self.assertIsNone(deal.closed_on)
        self.assertEqual(
            deal.pretty_status, "Offen seit {}".format(local_date_format(date.today()))
        )
