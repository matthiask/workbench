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
        self.assertContains(
            response,
            "Anfangswert von &#39;Kunde&#39; war &#39;The Organization Ltd&#39;.",
        )
        self.assertContains(
            response, "&#39;Typ&#39; änderte von &#39;Auftrag&#39; zu &#39;Intern&#39;."
        )
        self.assertContains(
            response,
            "Geschlossen am&#39; änderte von &#39;&lt;kein Wert&gt;&#39;"
            " zu &#39;01.01.2019&#39;.",
        )
