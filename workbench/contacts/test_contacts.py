from django.test import TestCase

from workbench import factories
from workbench.contacts.models import Group
from workbench.tools.testing import messages


def person_to_dict(person, **kwargs):
    return {
        "address": person.address,
        "given_name": person.given_name,
        "family_name": person.family_name,
        "address_on_first_name_terms": person.address_on_first_name_terms,
        "salutation": person.salutation,
        "notes": person.notes,
        "organization": person.organization_id or "",
        "primary_contact": person.primary_contact_id,
        "groups": person.groups.values_list("id", flat=True),
        "is_archived": person.is_archived,
        "phonenumbers-TOTAL_FORMS": 0,
        "phonenumbers-INITIAL_FORMS": 0,
        "phonenumbers-MAX_NUM_FORMS": 1000,
        "emailaddresses-TOTAL_FORMS": 0,
        "emailaddresses-INITIAL_FORMS": 0,
        "emailaddresses-MAX_NUM_FORMS": 1000,
        "postaladdresses-TOTAL_FORMS": 0,
        "postaladdresses-INITIAL_FORMS": 0,
        "postaladdresses-MAX_NUM_FORMS": 1000,
        **kwargs,
    }


class ContactsTest(TestCase):
    def test_update(self):
        person = factories.PersonFactory.create()
        self.client.force_login(person.primary_contact)
        response = self.client.post(person.urls["update"], person_to_dict(person))
        self.assertContains(
            response, "Keine Begrüssung gesetzt. Das macht Newsletter hässlich."
        )

        response = self.client.post(
            person.urls["update"], person_to_dict(person, salutation="Dear John")
        )
        self.assertRedirects(response, person.urls["detail"])

    def test_warning(self):
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create(), salutation="Dear John"
        )
        factories.ProjectFactory.create(customer=person.organization, contact=person)

        self.client.force_login(person.primary_contact)
        response = self.client.post(
            person.urls["update"], person_to_dict(person, organization="")
        )
        # print(response, response.content.decode("utf-8"))
        self.assertContains(
            response,
            "Diese Person ist der Kontakt der folgenden zugehörigen Objekte:"
            " 1 Projekt.",
        )

        factories.Project.objects.all().delete()
        response = self.client.post(
            person.urls["update"], person_to_dict(person, organization="")
        )
        self.assertRedirects(response, person.urls["detail"])
        self.assertEqual(
            messages(response),
            ["Person 'Vorname Nachname' wurde erfolgreich geändert."],
        )

    def test_lists(self):
        factories.PersonFactory.create()
        person = factories.PersonFactory.create()
        group1 = Group.objects.create(title="A")
        group2 = Group.objects.create(title="B")
        person.groups.set([group1])

        person = factories.PersonFactory.create(is_archived=True)

        self.client.force_login(person.primary_contact)
        response = self.client.get(person.urls["list"])
        self.assertContains(response, "1 &ndash; 2 von 2")
        self.assertContains(response, "Vorname Nachname", 2)

        response = self.client.get("/contacts/people/?g=" + str(group1.pk))
        self.assertContains(response, person.full_name)

        response = self.client.get("/contacts/people/?g=" + str(group2.pk))
        self.assertNotContains(response, person.full_name)

        response = self.client.get("/contacts/people/?xlsx=1")
        self.assertEqual(response.status_code, 200)

    def test_organization_list(self):
        group1 = Group.objects.create(title="A")
        group2 = Group.objects.create(title="B")
        organization = factories.OrganizationFactory.create()
        organization.groups.set([group1])
        person = factories.PersonFactory.create(organization=organization)

        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/contacts/organizations/")
        self.assertContains(response, str(organization))
        self.assertContains(response, person.full_name)

        response = self.client.get("/contacts/organizations/?g=" + str(group1.pk))
        self.assertContains(response, str(organization))

        response = self.client.get("/contacts/organizations/?g=" + str(group2.pk))
        self.assertNotContains(response, str(organization))

    def test_formset(self):
        person = factories.PersonFactory.create()
        person.emailaddresses.create(type="E1", email="e1@example.com")
        person.emailaddresses.create(type="E2", email="e2@example.com")
        person.emailaddresses.create(type="E3", email="e3@example.com")

        self.client.force_login(person.primary_contact)
        response = self.client.get(person.urls["update"])
        # print(response, response.content.decode("utf-8"))

        self.assertContains(response, "id_emailaddresses-0-email")
        self.assertContains(response, "id_emailaddresses-1-email")
        self.assertContains(response, "id_emailaddresses-2-email")
        self.assertContains(response, "e1@example.com")
        self.assertContains(response, "e2@example.com")
        self.assertContains(response, "e3@example.com")

    def test_details(self):
        person = factories.PersonFactory.create()
        email = person.emailaddresses.create(email="test@example.com")
        phone = person.phonenumbers.create(phone_number="012 345 678")
        address = person.postaladdresses.create(postal_address_override="A\nB")

        self.assertEqual(str(email), "test@example.com")
        self.assertEqual(str(phone), "012 345 678")
        self.assertEqual(str(address), "A\nB")

        for detail in [email, phone, address]:
            self.assertEqual(detail.get_absolute_url(), person.get_absolute_url())
            self.assertEqual(detail.urls["detail"], person.urls["detail"])

    def test_weights(self):
        person = factories.PersonFactory.create()
        email = person.emailaddresses.create(email="test@example.com")

        email.type = "mobil"
        email.save()
        self.assertEqual(email.weight, 30)

        email.type = "office"
        email.save()
        self.assertEqual(email.weight, 0)

        email.type = "zuhause"
        email.save()
        self.assertEqual(email.weight, 10)

        email.type = "Arbeit"
        email.save()
        self.assertEqual(email.weight, 20)

        email.type = "Firmenadresse"
        email.save()
        self.assertEqual(email.weight, -100)

    def test_contacts_redirect(self):
        self.client.force_login(factories.UserFactory.create())
        self.assertRedirects(self.client.get("/contacts/"), "/contacts/people/")
