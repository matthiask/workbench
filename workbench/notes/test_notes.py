import datetime as dt

from django.contrib.contenttypes.models import ContentType
from django.core import mail
from django.test import TestCase
from django.test.utils import override_settings
from django.utils.translation import deactivate_all

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.accounts.middleware import set_user_name
from workbench.notes.admin import content_object_url
from workbench.notes.models import Note
from workbench.notes.tasks import send_notes_digest
from workbench.tools.testing import check_code


class NotesTest(TestCase):
    def setUp(self):
        deactivate_all()

    def test_list(self):
        """Notes listing"""
        deal = factories.DealFactory.create()
        Note.objects.create(content_object=deal, created_by=deal.owned_by, title="Test")
        self.client.force_login(deal.owned_by)

        code = check_code(self, "/notes/")
        code("")

    def test_list_search(self):
        """The notes list can be searched and filtered, and leaves out notes
        the user may not see"""
        user = factories.UserFactory.create()
        deal = factories.DealFactory.create()
        invoice = factories.InvoiceFactory.create()
        Note.objects.create(
            content_object=deal,
            created_by=user,
            title="Call with the board",
            description="Budget approved",
        )
        Note.objects.create(
            content_object=invoice,
            created_by=invoice.owned_by,
            title="Payment reminder",
            description="Customer promised to pay next week",
        )
        self.client.force_login(user)

        def titles(query=""):
            response = self.client.get(f"/notes/{query}")
            self.assertEqual(response.status_code, 200)
            return [
                title
                for title in ["Call with the board", "Payment reminder"]
                if title in response.content.decode()
            ]

        self.assertEqual(titles(), ["Call with the board", "Payment reminder"])
        self.assertEqual(titles("?q=budget"), ["Call with the board"])
        self.assertEqual(titles("?q=pay"), ["Payment reminder"])
        self.assertEqual(titles("?type=invoice"), ["Payment reminder"])
        self.assertEqual(titles("?created_by=-1"), ["Call with the board"])
        self.assertEqual(
            titles(f"?created_by={invoice.owned_by.pk}"), ["Payment reminder"]
        )

        with override_settings(
            FEATURES={FEATURES.CONTROLLING: F.NEVER, FEATURES.DEALS: F.ALWAYS}
        ):
            self.assertEqual(titles(), ["Call with the board"])
            # Not offered as a choice anymore
            self.assertEqual(self.client.get("/notes/?type=invoice").status_code, 302)

    def test_form(self):
        """Assigning a note to a content object works as expected"""
        deal = factories.DealFactory.create()
        self.client.force_login(deal.owned_by)

        content_type = ContentType.objects.get_for_model(deal)
        add_url = (
            f"/notes/add-note/?content_type={content_type.pk}&amp;object_id={deal.pk}"
        )
        self.assertContains(self.client.get(deal.urls["detail"]), add_url)

        # The form opens in a modal
        response = self.client.get(
            add_url.replace("&amp;", "&"),
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertContains(response, f'value="{content_type.pk}"')
        self.assertContains(response, f'value="{deal.pk}"')
        self.assertNotContains(response, "Delete")

        response = self.client.post(
            "/notes/add-note/",
            {
                "content_type": content_type.pk,
                "object_id": deal.pk,
                "title": "Test title",
                "description": "Test description",
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 299)
        self.assertEqual(
            response.json(), {"redirect": Note.objects.get().get_absolute_url()}
        )

        # Errors are shown in the modal
        response = self.client.post(
            "/notes/add-note/",
            {
                "content_type": content_type.pk,
                "object_id": deal.pk + 1,
                "title": "Test title",
                "description": "",
            },
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "Unable to determine the object this note should be added to."
        )
        self.assertContains(response, "This field is required.")

        # print(response, response.content.decode("utf-8"))

        note = Note.objects.get()
        response = self.client.post(
            note.urls["update"],
            {"title": "Updated", "description": note.description},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)

        note.refresh_from_db()
        self.assertEqual(note.title, "Updated")

    def test_form_features_and_targets(self):
        """Notes are only added to, changed and deleted on objects whose notes
        the user may see"""
        invoice = factories.InvoiceFactory.create()
        offer = factories.OfferFactory.create()
        note = Note.objects.create(
            content_object=invoice, title="Payment", created_by=invoice.owned_by
        )
        self.client.force_login(invoice.owned_by)
        headers = {"x-requested-with": "XMLHttpRequest"}

        def add(obj):
            return self.client.post(
                "/notes/add-note/",
                {
                    "content_type": ContentType.objects.get_for_model(obj).pk,
                    "object_id": obj.pk,
                    "title": "Test",
                    "description": "Test",
                },
                headers=headers,
            )

        # Offers have no notes
        self.assertEqual(add(offer).status_code, 200)

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER}):
            self.assertEqual(add(invoice).status_code, 200)
            for url in [note.urls["update"], note.urls["delete"]]:
                with self.subTest(url=url):
                    response = self.client.get(url, headers=headers)
                    self.assertNotIn(b"Payment", response.content)

        self.assertEqual(Note.objects.count(), 1)

    def test_project_notes(self):
        """Projects have notes too, e.g. for debriefings"""
        project = factories.ProjectFactory.create()
        self.client.force_login(project.owned_by)
        content_type = ContentType.objects.get_for_model(project)

        self.assertContains(
            self.client.get(project.urls["detail"]),
            f"/notes/add-note/?content_type={content_type.pk}&amp;object_id={project.pk}",
        )

        response = self.client.post(
            "/notes/add-note/",
            {
                "content_type": content_type.pk,
                "object_id": project.pk,
                "title": "Debriefing",
                "description": "The prototype made the implementation predictable.",
            },
        )
        self.assertRedirects(response, Note.objects.latest("pk").get_absolute_url())
        self.assertContains(
            self.client.get(project.urls["detail"]),
            "The prototype made the implementation predictable.",
        )

        # Notes are Markdown
        Note.objects.create(
            content_object=project,
            created_by=project.owned_by,
            title="Next steps",
            description="- **Workshop** with <the customer>",
        )
        self.assertContains(
            self.client.get(project.urls["detail"]),
            "<li><strong>Workshop</strong> with &lt;the customer&gt;</li>",
        )

    def test_notes_digest(self):
        """Owners get one daily mail with the notes others added to or edited
        on their objects, not one mail per note; descriptions are truncated"""
        deal = factories.DealFactory.create(title="Big deal")
        project = factories.ProjectFactory.create(owned_by=deal.owned_by)
        own_project = factories.ProjectFactory.create()
        colleague = factories.UserFactory.create(_short_name="col")

        content_type = ContentType.objects.get_for_model(deal)
        self.client.force_login(colleague)
        response = self.client.post(
            "/notes/add-note/",
            {
                "content_type": content_type.pk,
                "object_id": deal.pk,
                "title": "Budget approved",
                "description": "Details " + "word " * 50 + "hidden",
            },
        )
        self.assertRedirects(response, Note.objects.latest("pk").get_absolute_url())
        self.assertEqual(len(mail.outbox), 0)

        set_user_name(colleague)
        on_project = Note.objects.create(
            content_object=project, created_by=colleague, title="Debriefing"
        )
        # Notes on objects the author owns and notes of the owner don't count
        set_user_name(own_project.owned_by)
        Note.objects.create(
            content_object=own_project,
            created_by=own_project.owned_by,
            title="Own note",
        )
        set_user_name(deal.owned_by)
        Note.objects.create(content_object=deal, created_by=deal.owned_by, title="Mine")

        send_notes_digest(day=dt.date.today())

        self.assertEqual(len(mail.outbox), 1)
        [message] = mail.outbox
        self.assertEqual(message.to, [deal.owned_by.email])
        self.assertIn("Budget approved", message.body)
        self.assertIn("Debriefing", message.body)
        self.assertIn(f"{on_project.get_absolute_url()}", message.body)
        # The description is truncated
        self.assertIn("Details word word", message.body)
        self.assertNotIn("hidden", message.body)
        self.assertNotIn("Mine", message.body)
        self.assertNotIn("Own note", message.body)

        # Edits by others are reported, too; yesterday's actions are not
        mail.outbox.clear()
        set_user_name(colleague)
        on_project.title = "Debriefing (edited)"
        on_project.save()
        send_notes_digest(day=dt.date.today() - dt.timedelta(days=1))
        self.assertEqual(len(mail.outbox), 0)
        send_notes_digest(day=dt.date.today())
        self.assertIn("Debriefing (edited)", mail.outbox[0].body)

    def test_notes_digest_inactive_owner(self):
        """Inactive owners and deleted notes are left out"""
        project = factories.ProjectFactory.create(
            owned_by=factories.UserFactory.create(is_active=False)
        )
        other = factories.ProjectFactory.create()
        colleague = factories.UserFactory.create()
        set_user_name(colleague)
        Note.objects.create(content_object=project, created_by=colleague, title="A")
        Note.objects.create(
            content_object=other, created_by=colleague, title="B"
        ).delete()

        send_notes_digest(day=dt.date.today())
        self.assertEqual(len(mail.outbox), 0)

    def test_content_object_url(self):
        """The content_object_url admin helper works"""
        # Has URL
        deal = factories.DealFactory.create()
        content_type = ContentType.objects.get_for_model(deal)

        self.assertEqual(
            content_object_url(Note(content_type=content_type, object_id=42, pk=3)),
            '<a href="/deals/42/#note-3">deal</a>',
        )

        # No URL
        types = factories.service_types()
        content_type = ContentType.objects.get_for_model(types.consulting)

        self.assertEqual(
            content_object_url(Note(content_type=content_type, object_id=42)),
            "service type",
        )
