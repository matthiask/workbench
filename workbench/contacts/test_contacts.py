import datetime as dt

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings

from workbench import factories
from workbench.contacts.models import Group, Organization, Person, PhoneNumber
from workbench.contacts.urls import autocomplete_filter
from workbench.tools.testing import messages
from workbench.tools.vcard import person_to_vcard


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
        """A single-word salutation does not look right"""
        person = factories.PersonFactory.create()
        self.client.force_login(person.primary_contact)
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
        """Changing the organization of a person with projects produces a warning"""
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
            ["Person 'Vorname Nachname' has been updated successfully."],
        )

    def test_lists(self):
        """The people list basically works"""
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

        response = self.client.get("/contacts/people/?export=xlsx")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/contacts/people/?export=vcard")
        self.assertEqual(response.status_code, 200)

    def test_organization_list(self):
        """The organization list basically works"""
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
        """The emails formset works"""
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
        """Common methods of person details do the right thing"""
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
        """Test weighting depending on the type of person details"""
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
        """Accessing /contacts/ (not linked anywhere) redirects"""
        self.client.force_login(factories.UserFactory.create())
        self.assertRedirects(self.client.get("/contacts/"), "/contacts/people/")

    def test_phone_numbers(self):
        """Phone number validation"""
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
        """The person select popup returns a redirect JSON"""
        person = factories.PersonFactory.create()
        self.client.force_login(person.primary_contact)

        response = self.client.get(person.urls["select"])
        self.assertContains(
            response, 'data-autocomplete-url="/contacts/people/autocomplete/"'
        )

        response = self.client.post(person.urls["select"], {"modal-person": person.pk})
        self.assertEqual(response.status_code, 299)
        self.assertEqual(response.json(), {"redirect": person.get_absolute_url()})

    def test_phone_number_formatting(self):
        """Phone numbers are formatted correctly, no crash on invalid data"""
        pn = PhoneNumber()
        pn.phone_number = "+41791234567"
        self.assertEqual(pn.pretty_number, "+41 79 123 45 67")
        pn.phone_number = "abcd"  # Completely bogus
        self.assertEqual(pn.pretty_number, "abcd")

    def test_person_create_redirect(self):
        """Creating persons redirects to their update page (for adding details)"""
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
        """Organizations without relations can be deleted"""
        organization = factories.OrganizationFactory.create()
        self.client.force_login(organization.primary_contact)

        response = self.client.get(organization.urls["delete"])
        self.assertNotContains(response, "substitute_with")

        response = self.client.post(organization.urls["delete"])
        self.assertRedirects(response, organization.urls["list"])

        self.assertEqual(Organization.objects.count(), 0)

    def test_organization_delete_with_relations(self):
        """Organizations with relations can be merged with a different org."""
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

    def test_create_person_with_preselected_organization(self):
        """Adding a person to an existing org. preselects the organization"""
        organization = factories.OrganizationFactory.create(name="ABCD")
        self.client.force_login(organization.primary_contact)

        response = self.client.get(
            Person.urls["create"] + "?organization={}".format(organization.pk)
        )
        self.assertContains(response, 'value="ABCD"')

    def test_organization_detail(self):
        """The organization detail page contains a few additional headings
        depending on the controlling feature"""
        organization = factories.OrganizationFactory.create()
        self.client.force_login(organization.primary_contact)

        response = self.client.get(organization.urls["detail"])
        self.assertContains(response, "Recent projects")
        self.assertContains(response, "Recent invoices")
        self.assertContains(response, "Recent offers")

        with override_settings(FEATURES={"controlling": False}):
            response = self.client.get(organization.urls["detail"])
            self.assertContains(response, "Recent projects")
            self.assertNotContains(response, "Recent invoices")
            self.assertNotContains(response, "Recent offers")

    def test_vcard_export(self):
        """Persons' details can be exported as a vCard or mailed to iOS users"""
        person = factories.PersonFactory.create()
        self.client.force_login(person.primary_contact)

        response = self.client.get(person.urls["vcard"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["content-type"], "text/x-vCard;charset=utf-8")

        self.assertEqual(len(mail.outbox), 0)
        response = self.client.get(
            person.urls["vcard"],
            HTTP_REFERER=person.urls["detail"],
            HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",  # noqa
        )
        self.assertRedirects(response, person.urls["detail"])
        self.assertEqual(len(mail.outbox), 1)

    def test_vcard(self):
        """Test aspects of the generated vCard export"""
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create(),
            date_of_birth=dt.date(2020, 3, 1),
            notes="Bla",
        )

        factories.PostalAddressFactory.create(person=person)
        factories.PostalAddressFactory.create(
            person=person, postal_address_override="OVERRIDE"
        )
        person.emailaddresses.create(email="test@example.com", type="work")
        person.phonenumbers.create(phone_number="012 345 678", type="work")

        serialized = person_to_vcard(person).serialize()
        self.assertIn("OVERRIDE", serialized)
        self.assertIn("2020-03-01", serialized)

    def test_maps_url(self):
        """Person.get_maps_url returns a maps URL"""
        address = factories.PostalAddressFactory.build()
        self.assertIn("google.com/maps", address.get_maps_url())

        address = factories.PostalAddress()
        self.assertIsNone(address.get_maps_url())

    def test_person_stringification(self):
        """Persons' and postal addresses' string representation matches expectations"""

        organization = factories.OrganizationFactory.build(name="Employer A")
        person = factories.PersonFactory.build(
            organization=organization, given_name="Hans", family_name="Wurst"
        )

        self.assertEqual(str(person), "Hans Wurst")
        self.assertEqual(person.name_with_organization, "Employer A / Hans Wurst")

        home = factories.PostalAddressFactory.build(
            person=person,
            type="home",
            street="Street",
            house_number="42",
            postal_code="8000",
            city="Zürich",
        )

        work = factories.PostalAddressFactory.build(
            person=person,
            type="work",
            street="Other street",
            house_number="42",
            postal_code="8000",
            city="Zürich",
        )

        self.assertEqual(
            home.postal_address,
            """\
Hans Wurst
Street 42
8000 Zürich""",
        )

        self.assertEqual(
            work.postal_address,
            """\
Employer A
Hans Wurst
Other street 42
8000 Zürich""",
        )

        organization.is_private_person = True
        self.assertEqual(
            work.postal_address,
            """\
Hans Wurst
Other street 42
8000 Zürich""",
        )

        person = factories.PersonFactory.build(given_name="Fritz", family_name="Muster")
        self.assertEqual(str(person), "Fritz Muster")
        self.assertEqual(person.name_with_organization, "Fritz Muster")

    def test_autocomplete_filter(self):
        """autocomplete_filter test"""
        rf = RequestFactory()
        req = rf.get("/?only_employees=on")

        factories.PersonFactory.create()
        self.assertEqual(
            list(autocomplete_filter(request=req, queryset=Person.objects.all())), []
        )

    def test_archived_str(self):
        """__str__ of archived persons and organizations mentions the archival"""
        person = factories.PersonFactory.build(
            given_name="Test", family_name="Just", is_archived=True
        )
        self.assertEqual(str(person), "Test Just (archived)")

        organization = factories.OrganizationFactory.build(
            name="Test", is_archived=True
        )
        self.assertEqual(str(organization), "Test (archived)")
