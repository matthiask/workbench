from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.notes.models import Note


class NotesAPITest(TestCase):
    def tearDown(self):
        deactivate_all()

    def test_search(self):
        """All notes can be searched, or the notes of an object"""
        user = factories.UserFactory.create(_short_name="ab")
        deal = factories.DealFactory.create()
        invoice = factories.InvoiceFactory.create()
        on_deal = Note.objects.create(
            content_object=deal,
            created_by=user,
            title="Call",
            description="Budget approved by the board",
        )
        on_invoice = Note.objects.create(
            content_object=invoice,
            created_by=factories.UserFactory.create(),
            title="Reminder",
            description="Customer promised to pay next week",
        )
        self.client.force_login(user)

        def ids(query=""):
            return [
                n["id"] for n in self.client.get(f"/api/notes/{query}").json()["items"]
            ]

        self.assertEqual(ids(), [on_invoice.pk, on_deal.pk])
        self.assertEqual(ids("?q=budget"), [on_deal.pk])
        self.assertEqual(ids(f"?deal={deal.pk}"), [on_deal.pk])
        self.assertEqual(ids(f"?invoice={invoice.pk}"), [on_invoice.pk])
        self.assertEqual(
            ids(f"?deal={deal.pk}&invoice={invoice.pk}"), [on_invoice.pk, on_deal.pk]
        )
        self.assertEqual(ids("?created_by=AB"), [on_deal.pk])
        self.assertEqual(ids("?period=this-month"), [on_invoice.pk, on_deal.pk])
        self.assertEqual(ids("?period=last-year"), [])

        data = self.client.get(f"/api/notes/?deal={deal.pk}").json()["items"][0]
        self.assertEqual(data["created_by"], "ab")
        self.assertEqual(data["object"]["type"], "deal")
        self.assertEqual(data["object"]["id"], deal.pk)
        self.assertEqual(
            data["object"]["url"], f"http://testserver{deal.get_absolute_url()}"
        )

        # Notes on objects the user may not see are left out
        with override_settings(
            FEATURES={FEATURES.CONTROLLING: F.NEVER, FEATURES.DEALS: F.ALWAYS}
        ):
            self.assertEqual(ids(), [on_deal.pk])

    def test_deleted_objects(self):
        """Notes of deleted objects are left out"""
        user = factories.UserFactory.create()
        deal = factories.DealFactory.create()
        Note.objects.create(
            content_object=deal, created_by=user, title="Gone", description="Gone"
        )
        deal.delete()
        self.client.force_login(user)

        response = self.client.get("/api/notes/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"], [])

    def test_create(self):
        """Notes are added to exactly one object, its owner is notified"""
        deal = factories.DealFactory.create()
        self.client.force_login(factories.UserFactory.create())

        response = self.client.post(
            "/api/notes/",
            {"title": "Call", "description": "Budget approved", "deal": deal.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        note = Note.objects.get()
        self.assertEqual(note.content_object, deal)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [deal.owned_by.email])

        response = self.client.post(
            "/api/notes/",
            {"title": "Call", "description": "Budget approved"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

        response = self.client.post(
            "/api/notes/",
            {"title": "Call", "description": "Nope", "deal": 0},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 422)

        with override_settings(FEATURES={FEATURES.DEALS: F.NEVER}):
            response = self.client.post(
                "/api/notes/",
                {"title": "Call", "description": "Nope", "deal": deal.pk},
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Note.objects.count(), 1)
