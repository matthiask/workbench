from datetime import date

from django.test import TestCase

from workbench import factories
from workbench.accounts.middleware import set_user_name
from workbench.projects.models import Project
from workbench.tools import history


class HistoryTest(TestCase):
    def test_header(self):
        set_user_name("ballabla")
        user1 = factories.UserFactory.create(_full_name="foo")
        set_user_name("user-%d-%s" % (user1.id, user1.get_short_name()))
        user2 = factories.UserFactory.create(_full_name="bar")
        set_user_name("user-%d-%s" % (user2.id, user2.get_short_name()))
        user3 = factories.UserFactory.create()

        self.client.force_login(user1)

        response = self.client.get("/history/accounts.user/id/{}/".format(user1.pk))
        self.assertContains(response, "INSERT id:{} / ballabla /".format(user1.pk))

        response = self.client.get("/history/accounts.user/id/{}/".format(user2.pk))
        self.assertContains(response, "INSERT id:{} / foo /".format(user2.pk))

        response = self.client.get("/history/accounts.user/id/{}/".format(user3.pk))
        self.assertContains(response, "INSERT id:{} / bar /".format(user3.pk))

    def test_history(self):
        project = factories.ProjectFactory.create()
        project.owned_by = factories.UserFactory.create()
        project.type = Project.INTERNAL
        project.closed_on = date(2019, 1, 1)
        project.save()

        self.client.force_login(project.owned_by)
        response = self.client.get(
            "/history/projects.project/id/{}/".format(project.pk)
        )
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "Anfangswert von 'Kundschaft' war")
        self.assertContains(response, "The Organization Ltd")

    def test_contact_history(self):
        person = factories.PersonFactory.create()
        person.is_archived = True
        person.save()
        self.client.force_login(person.primary_contact)
        response = self.client.get("/history/contacts.person/id/{}/".format(person.pk))
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "'Ist archiviert' änderte von 'nein' zu 'ja'.")

    def test_related_history(self):
        pa = factories.PostalAddressFactory.create()
        self.client.force_login(pa.person.primary_contact)
        response = self.client.get(
            "/history/contacts.postaladdress/person_id/{}/".format(pa.person_id)
        )
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "INSERT id:{} /".format(pa.pk))

    def test_nothing(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/history/contacts.person/id/0/")
        # print(response, response.content.decode("utf-8"))
        self.assertContains(response, "Keine Geschichte gefunden")

    def test_deleted(self):
        organization = factories.OrganizationFactory.create()
        person = factories.PersonFactory.create(organization=organization)
        person.organization = None
        person.save()
        pk = organization.pk
        organization.delete()

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/history/contacts.person/id/{}/".format(person.pk))
        self.assertContains(
            response,
            '<a href="/history/contacts.organization/id/{}/" data-toggle="ajaxmodal">'
            "Gelöschte Organisation-Instanz</a>".format(pk),
        )

        response = self.client.get("/history/contacts.organization/id/{}/".format(pk))
        self.assertContains(
            response, "Finaler Wert von 'Name' war 'The Organization Ltd'."
        )
        # print(response, response.content.decode("utf-8"))

    def test_exclusion(self):
        service = factories.ServiceFactory.create()
        service.position += 1
        service.save()
        service.position += 1
        service.save()
        service.title += " test"
        service.save()

        self.client.force_login(service.project.owned_by)
        response = self.client.get(
            "/history/projects.service/id/{}/".format(service.id)
        )
        self.assertContains(response, "INSERT")
        # Only two versions -- position changes are excluded
        self.assertContains(response, "UPDATE", 1)

    def test_nocrash(self):
        # Do not crash when encountering invalid values.
        self.assertEqual(history.boolean_formatter("stuff"), "stuff")
        self.assertEqual(history.date_formatter("stuff"), "stuff")
