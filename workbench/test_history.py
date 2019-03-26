from datetime import date

from django.test import TestCase

from workbench import factories
from workbench.projects.models import Project


class HistoryTest(TestCase):
    def test_history(self):
        project = factories.ProjectFactory.create()
        project.owned_by = factories.UserFactory.create()
        project.type = Project.INTERNAL
        project.closed_on = date(2019, 1, 1)
        project.save()

        self.client.force_login(project.owned_by)
        response = self.client.get("/history/projects.project/{}/".format(project.pk))
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "Version 2")
        self.assertContains(
            response,
            "Anfangswert von 'Kunde' war",
        )
        self.assertContains(
            response,
            "The Organization Ltd",
        )

    def test_contact_history(self):
        person = factories.PersonFactory.create()
        person.is_archived = True
        person.save()
        self.client.force_login(person.primary_contact)
        response = self.client.get("/history/contacts.person/{}/".format(person.pk))
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "Version 2")
        self.assertContains(
            response,
            "'Ist archiviert' änderte von 'nein' zu 'ja'.",
        )

    def test_nothing(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/history/contacts.person/0/")
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "Keine Geschichte gefunden")
