import datetime as dt

from django.db.models import ProtectedError
from django.test import TestCase
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.tools.formats import local_date_format


class DealsTest(TestCase):
    def setUp(self):
        deactivate_all()

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
        deal.values.create(type=factories.ValueTypeFactory.create(), value=42)
        deal.save()

        self.client.force_login(deal.owned_by)
        response = self.client.get(deal.urls["detail"])
        # print(response, response.content.decode("utf-8"))
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
            },
        )
        self.assertEqual(response.status_code, 302)
        deal = factories.Deal.objects.get()
        self.assertIsNone(deal.closed_on)
        self.assertEqual(
            deal.pretty_status,
            "Open since {}".format(local_date_format(dt.date.today())),
        )

        response = self.client.post(
            deal.urls["set_status"],
            {
                "status": factories.Deal.DECLINED,
                "closing_type": factories.ClosingTypeFactory.create(
                    represents_a_win=False
                ).pk,
            },
        )
        self.assertRedirects(response, deal.urls["detail"])

        deal.refresh_from_db()
        self.assertEqual(deal.closed_on, dt.date.today())
        self.assertEqual(
            deal.pretty_status,
            "declined on {}".format(local_date_format(dt.date.today())),
        )

        response = self.client.post(
            deal.urls["set_status"], {"status": factories.Deal.OPEN},
        )
        self.assertRedirects(response, deal.urls["detail"])

        deal.refresh_from_db()
        self.assertIsNone(deal.closed_on)
        self.assertEqual(
            deal.pretty_status,
            "Open since {}".format(local_date_format(dt.date.today())),
        )

    def test_protected_m2m(self):
        deal = factories.DealFactory.create()
        group = factories.AttributeGroupFactory.create()
        value = group.values.create(title="Test", position=0)
        deal.attributes.add(value)

        with self.assertRaises(ProtectedError):
            group.delete()
