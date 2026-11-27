import datetime as dt

from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.notes.models import Note
from workbench.notes.tasks import send_notes_digest


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

    def test_project(self):
        """Notes on projects need no feature"""
        project = factories.ProjectFactory.create(title="Relaunch")
        other = factories.ProjectFactory.create()
        self.client.force_login(factories.UserFactory.create())

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER}):
            response = self.client.post(
                "/api/notes/",
                {
                    "title": "Debriefing",
                    "description": "Prototype first",
                    "project": project.pk,
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content)
            Note.objects.create(
                content_object=other, created_by=other.owned_by, title="Other"
            )

            data = self.client.get("/api/notes/", {"project": project.pk}).json()
        [note] = data["items"]
        self.assertEqual(note["title"], "Debriefing")
        self.assertEqual(note["object"]["type"], "project")
        self.assertEqual(note["object"]["id"], project.pk)
        self.assertIn("Relaunch", note["object"]["name"])

    def test_create(self):
        """Notes are added to exactly one object, without an immediate mail"""
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
        self.assertEqual(len(mail.outbox), 0)

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

    def test_show(self):
        """Single notes, only those the user may see"""
        deal = factories.DealFactory.create(title="Relaunch")
        note = Note.objects.create(
            content_object=deal, created_by=deal.owned_by, title="Call"
        )
        self.client.force_login(factories.UserFactory.create())

        data = self.client.get(f"/api/notes/{note.pk}/").json()
        self.assertEqual(data["id"], note.pk)
        self.assertEqual(data["title"], "Call")
        self.assertEqual(data["object"]["type"], "deal")

        with override_settings(FEATURES={FEATURES.DEALS: F.NEVER}):
            response = self.client.get(f"/api/notes/{note.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get("/api/notes/0/").status_code, 404)

    def test_update(self):
        """Notes of others can be changed like in the web interface, without
        an immediate mail; dry runs save nothing"""
        deal = factories.DealFactory.create()
        note = Note.objects.create(
            content_object=deal,
            created_by=deal.owned_by,
            title="Call",
            description="Budget approved",
        )
        self.client.force_login(factories.UserFactory.create())

        def patch(data, query=""):
            return self.client.patch(
                f"/api/notes/{note.pk}/{query}", data, content_type="application/json"
            )

        response = patch({"title": "Phone call"}, "?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Phone call")
        note.refresh_from_db()
        self.assertEqual(note.title, "Call")

        response = patch({"description": "Budget approved by the board"})
        self.assertEqual(response.status_code, 200, response.content)
        note.refresh_from_db()
        self.assertEqual(note.title, "Call")
        self.assertEqual(note.description, "Budget approved by the board")
        self.assertEqual(note.created_by, deal.owned_by)
        self.assertEqual(len(mail.outbox), 0)
        # The owner finds the change in the daily digest
        send_notes_digest(day=dt.date.today())
        [message] = mail.outbox
        self.assertEqual(message.to, [deal.owned_by.email])
        self.assertIn("Budget approved by the board", message.body)

        response = patch({"title": None})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"][0]["loc"], ["body", "data", "title"])
        # Notes aren't moved to other objects
        self.assertEqual(patch({"deal": deal.pk}).status_code, 422)

        with override_settings(FEATURES={FEATURES.DEALS: F.NEVER}):
            self.assertEqual(patch({"title": "Nope"}).status_code, 404)
        note.refresh_from_db()
        self.assertEqual(note.title, "Call")

    def test_delete(self):
        """Notes of others can be deleted like in the web interface"""
        invoice = factories.InvoiceFactory.create()
        note = Note.objects.create(
            content_object=invoice, created_by=invoice.owned_by, title="Reminder"
        )
        self.client.force_login(factories.UserFactory.create())

        response = self.client.delete(f"/api/notes/{note.pk}/?dry_run=1")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Reminder")
        self.assertTrue(Note.objects.filter(pk=note.pk).exists())

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER}):
            response = self.client.delete(f"/api/notes/{note.pk}/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Note.objects.filter(pk=note.pk).exists())

        response = self.client.delete(f"/api/notes/{note.pk}/")
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["id"], note.pk)
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())
        self.assertEqual(len(mail.outbox), 0)
