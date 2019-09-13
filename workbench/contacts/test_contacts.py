from django.core.exceptions import ValidationError
from django.test import TestCase

from workbench import factories
from workbench.contacts.models import Group, Organization, Person, PhoneNumber
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
            response, "No salutation set. This will make newsletters ugly."
        )

        response = self.client.post(
            person.urls["update"], person_to_dict(person, salutation="Dear")
        )
        self.assertContains(
            response, "This does not look right. Please add a full salutation."
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
            "This person is the contact of the following related objects:"
            " 1 project.",
        )

        factories.Project.objects.all().delete()
        response = self.client.post(
            person.urls["update"], person_to_dict(person, organization="")
        )
        self.assertRedirects(response, person.urls["detail"])
        self.assertEqual(
            messages(response),
            ["person 'Vorname Nachname' has been updated successfully."],
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
        self.assertContains(response, "1 &ndash; 2 of 2")
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

    def test_phone_numbers(self):
        person = factories.PersonFactory.create()
        kw = {"person": person, "type": "work"}
        with self.assertRaises(ValidationError):
            PhoneNumber(phone_number="+41 555 11 11 41 41", **kw).full_clean()
        with self.assertRaises(ValidationError):
            PhoneNumber(phone_number="+41 555 11 11 4", **kw).full_clean()
        with self.assertRaises(ValidationError):
            PhoneNumber(phone_number="just some stuff", **kw).full_clean()

        nr = PhoneNumber(phone_number="+41 555 11 11 41", **kw)
        nr.full_clean()
        self.assertEqual(nr.phone_number, "+41555111141")

        nr = PhoneNumber(phone_number="055 511 11 41", **kw)
        nr.full_clean()
        self.assertEqual(nr.phone_number, "+41555111141")

    def test_select(self):
        person = factories.PersonFactory.create()
        self.client.force_login(person.primary_contact)

        response = self.client.get(person.urls["select"])
        self.assertContains(
            response, 'data-autocomplete-url="/contacts/people/autocomplete/"'
        )

        response = self.client.post(person.urls["select"], {"person-person": person.pk})
        self.assertEqual(response.status_code, 299)
        self.assertEqual(response.json(), {"redirect": person.get_absolute_url()})

    def test_phone_number_formatting(self):
        pn = PhoneNumber()
        pn.phone_number = "+41791234567"
        self.assertEqual(pn.pretty_number, "+41 79 123 45 67")
        pn.phone_number = "abcd"  # Completely bogus
        self.assertEqual(pn.pretty_number, "abcd")

    def test_person_create_redirect(self):
        user = factories.UserFactory.create()
        self.client.force_login(user)

        response = self.client.post(
            "/contacts/people/create/",
            {
                "given_name": "Test",
                "family_name": "Jones",
                "salutation": "Hi Mr. Jones",
                "primary_contact": user.pk,
            },
        )
        self.assertEqual(response.status_code, 302)

        person = Person.objects.get()
        self.assertRedirects(response, person.urls["update"])

    def test_organization_delete_without_relations(self):
        organization = factories.OrganizationFactory.create()
        self.client.force_login(organization.primary_contact)

        response = self.client.get(organization.urls["delete"])
        self.assertNotContains(response, "substitute_with")

        response = self.client.post(organization.urls["delete"])
        self.assertRedirects(response, organization.urls["list"])

        self.assertEqual(Organization.objects.count(), 0)

    def test_organization_delete_with_relations(self):
        organization = factories.OrganizationFactory.create()
        person = factories.PersonFactory.create(organization=organization)
        self.client.force_login(organization.primary_contact)

        group = Group.objects.create(title="A")
        organization.groups.set([group])

        response = self.client.get(organization.urls["delete"])
        self.assertContains(response, "substitute_with")

        response = self.client.post(organization.urls["delete"])
        self.assertEqual(response.status_code, 200)

        new = factories.OrganizationFactory.create()
        response = self.client.post(
            organization.urls["delete"], {"substitute_with": new.pk}
        )
        self.assertRedirects(response, organization.urls["list"])

        self.assertEqual(Organization.objects.count(), 1)

        person.refresh_from_db()
        self.assertEqual(person.organization, new)
        self.assertEqual(new.groups.count(), 0)  # Group (m2m) not assigned
