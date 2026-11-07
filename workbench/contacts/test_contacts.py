import datetime as dt
import io
from unittest import mock

from django.core import mail
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.utils import timezone
from django.utils.translation import deactivate_all
from openpyxl import load_workbook

from workbench import factories
from workbench.accounts.features import FEATURES, F
from workbench.audit.models import LoggedAction
from workbench.contacts import tasks
from workbench.contacts.forms import GroupSearchForm
from workbench.contacts.merge import merge_people
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
    def setUp(self):
        deactivate_all()

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
            "This person is the contact of the following related objects: 1 project.",
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
        self.assertContains(response, "1 &ndash; 2 of 2", html=True)
        self.assertContains(response, "Vorname Nachname", 2)

        response = self.client.get("/contacts/people/?g=" + str(group1.pk))
        self.assertContains(response, person.full_name)

        response = self.client.get("/contacts/people/?g=" + str(group2.pk))
        self.assertNotContains(response, person.full_name)

        response = self.client.get("/contacts/people/?export=xlsx")
        self.assertEqual(response.status_code, 200)

        response = self.client.get("/contacts/people/?export=vcard")
        self.assertEqual(response.status_code, 200)

    def test_people_xlsx_export(self):
        """The export of the people list has the columns of a mailing list
        first, and the group and the date in the file name"""
        group = Group.objects.create(title="Christmas Mailing")
        person = factories.PersonFactory.create(
            given_name="Hans",
            family_name="Muster",
            organization=factories.OrganizationFactory.create(name="Beispiel AG"),
        )
        person.groups.add(group)
        person.postaladdresses.create(
            street="Hauptstrasse",
            house_number="1",
            postal_code="8000",
            city="Zürich",
            country="CH",
        )
        person.emailaddresses.create(email="hans@example.com")
        self.client.force_login(person.primary_contact)

        response = self.client.get(f"/contacts/people/?g={group.pk}&export=xlsx")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            f'filename="people-christmas-mailing-{dt.date.today().isoformat()}.xlsx"',
            response["content-disposition"],
        )
        sheet = load_workbook(io.BytesIO(response.content)).active
        header, row = ([cell.value for cell in r] for r in sheet.iter_rows(max_row=2))
        header = [title.lower() for title in header]
        self.assertEqual(
            header[:11],
            [
                "primary contact",
                "organization",
                "given name",
                "family name",
                "street",
                "house number",
                "address suffix",
                "postal code",
                "city",
                "country",
                "override",
            ],
        )
        values = dict(zip(header, row, strict=True))
        self.assertEqual(
            values["primary contact"], person.primary_contact.get_full_name()
        )
        self.assertEqual(values["organization"], "Beispiel AG")
        self.assertEqual(values["country"], "CH")
        self.assertEqual(values["email"], "hans@example.com")
        self.assertEqual(values["groups"], "Christmas Mailing")

        response = self.client.get("/contacts/people/?export=xlsx")
        self.assertIn(
            f'filename="people-{dt.date.today().isoformat()}.xlsx"',
            response["content-disposition"],
        )

    def test_person_list_rows(self):
        """Rows show the organization and the active groups"""
        person = factories.PersonFactory.create(
            organization=factories.OrganizationFactory.create(name="Acme Ltd.")
        )
        person.groups.set([
            Group.objects.create(title="Newsletter"),
            Group.objects.create(title="Mailing 2015", is_archived=True),
        ])
        factories.PersonFactory.create(given_name="Groupless")

        self.client.force_login(person.primary_contact)
        with self.assertNumQueries(11):
            response = self.client.get(person.urls["list"])
        self.assertContains(response, "Acme Ltd.")
        self.assertContains(response, ">Newsletter</a>")
        self.assertNotContains(response, ">Mailing 2015</a>")

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

    def test_organization_list_status(self):
        """Organizations can be filtered by status and defined searches"""
        customer = factories.ProjectFactory.create(
            customer=factories.OrganizationFactory.create(name="Customer Ltd.")
        ).customer
        customer.groups.set([Group.objects.create(title="Customers")])
        factories.DealFactory.create(
            customer=factories.OrganizationFactory.create(name="Lead Ltd.")
        )
        factories.OrganizationFactory.create(name="Lonely Ltd.")
        factories.OrganizationFactory.create(name="Gone Ltd.", is_archived=True)

        self.client.force_login(factories.UserFactory.create())

        def names(query):
            response = self.client.get("/contacts/organizations/" + query)
            self.assertEqual(response.status_code, 200)
            return {
                organization.name for organization in response.context["object_list"]
            }

        active = {"Customer Ltd.", "Lead Ltd.", "Lonely Ltd."}
        self.assertEqual(names(""), active)
        self.assertEqual(names("?s=all"), active | {"Gone Ltd."})
        self.assertEqual(names("?s=any-projects-deals"), {"Customer Ltd.", "Lead Ltd."})
        self.assertEqual(names("?s=no-group"), {"Lead Ltd.", "Lonely Ltd."})
        self.assertEqual(names("?s=no-people"), {"Lonely Ltd."})

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

    def test_merge_people(self):
        """Merging moves relations, details and groups to the person to keep
        and drops details the person to keep has already"""
        keep = factories.PersonFactory.create(notes="Keep")
        duplicate = factories.PersonFactory.create(
            notes="Duplicate", date_of_birth=dt.date(1980, 1, 1)
        )
        project = factories.ProjectFactory.create(contact=duplicate)
        user = factories.UserFactory.create(person=duplicate)
        group = Group.objects.create(title="Christmas")
        duplicate.groups.add(group)
        keep.emailaddresses.create(email="carmen@example.com")
        duplicate.emailaddresses.create(email="Carmen@example.com")
        duplicate.emailaddresses.create(email="other@example.com")
        keep.phonenumbers.create(phone_number="+41441234567")
        duplicate.phonenumbers.create(phone_number="+41441234567")

        merge_people(duplicate=duplicate, keep=keep)

        self.assertFalse(Person.objects.filter(pk=duplicate.pk).exists())
        project.refresh_from_db()
        self.assertEqual(project.contact, keep)
        user.refresh_from_db()
        self.assertEqual(user.person, keep)
        keep.refresh_from_db()
        self.assertEqual(list(keep.groups.all()), [group])
        self.assertEqual(
            sorted(keep.emailaddresses.values_list("email", flat=True)),
            ["carmen@example.com", "other@example.com"],
        )
        self.assertEqual(keep.phonenumbers.count(), 1)
        self.assertEqual(keep.notes, "Keep\n\nDuplicate")
        self.assertEqual(keep.date_of_birth, dt.date(1980, 1, 1))
        self.assertIn("other@example.com", keep._fts)

    def test_merge_into_archived_person(self):
        """The person kept is only archived if both were archived"""
        for duplicate_archived, archived in [(False, False), (True, True)]:
            with self.subTest(duplicate_archived=duplicate_archived):
                keep = factories.PersonFactory.create(is_archived=True)
                duplicate = factories.PersonFactory.create(
                    is_archived=duplicate_archived
                )
                merge_people(duplicate=duplicate, keep=keep)
                keep.refresh_from_db()
                self.assertEqual(keep.is_archived, archived)

    def test_merge_people_linked_to_users(self):
        """People who are both linked to a user cannot be merged"""
        keep = factories.UserFactory.create(
            person=factories.PersonFactory.create()
        ).person
        duplicate = factories.UserFactory.create(
            person=factories.PersonFactory.create()
        ).person
        with self.assertRaises(ValidationError):
            merge_people(duplicate=duplicate, keep=keep)
        with self.assertRaises(ValidationError):
            merge_people(duplicate=keep, keep=keep)
        self.assertEqual(Person.objects.count(), 2)

    def test_person_delete_merge(self):
        """People can be deleted or merged into a different person, which is
        required if they are linked to a user"""
        person = factories.PersonFactory.create()
        self.client.force_login(person.primary_contact)

        response = self.client.get(person.urls["delete"])
        self.assertContains(response, "merge_into")
        response = self.client.post(person.urls["delete"])
        self.assertRedirects(response, person.urls["list"])
        self.assertEqual(Person.objects.count(), 0)

        person = factories.PersonFactory.create()
        project = factories.ProjectFactory.create(contact=person)
        factories.UserFactory.create(person=person)
        response = self.client.post(person.urls["delete"])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Person.objects.filter(pk=person.pk).exists())

        keep = factories.PersonFactory.create()
        response = self.client.post(person.urls["delete"], {"merge_into": keep.pk})
        self.assertRedirects(response, keep.urls["detail"])
        self.assertFalse(Person.objects.filter(pk=person.pk).exists())
        project.refresh_from_db()
        self.assertEqual(project.contact, keep)

    def test_create_person_with_preselected_organization(self):
        """Adding a person to an existing org. preselects the organization"""
        organization = factories.OrganizationFactory.create(name="ABCD")
        self.client.force_login(organization.primary_contact)

        response = self.client.get(
            Person.urls["create"] + f"?organization={organization.pk}"
        )
        self.assertContains(response, 'value="ABCD"')

    def test_organization_detail(self):
        """The organization detail page contains a few additional headings
        depending on the CONTROLLING feature"""
        organization = factories.OrganizationFactory.create()
        self.client.force_login(organization.primary_contact)

        response = self.client.get(organization.urls["detail"])
        self.assertContains(response, "Recent projects")
        self.assertContains(response, "Recent invoices")
        self.assertContains(response, "Recent offers")

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER}):
            response = self.client.get(organization.urls["detail"])
            self.assertContains(response, "Recent projects")
            self.assertNotContains(response, "Recent invoices")
            self.assertNotContains(response, "Recent offers")

    def test_person_detail(self):
        """The person detail page lists the projects, deals and invoices the
        person is the contact of"""
        project = factories.ProjectFactory.create(title="Relaunch")
        person = project.contact
        factories.DealFactory.create(contact=person, title="Pitch")
        self.client.force_login(person.primary_contact)

        response = self.client.get(person.urls["detail"])
        self.assertContains(response, "Relaunch")
        self.assertContains(response, "Pitch")
        self.assertContains(response, "Recent invoices")

        with override_settings(FEATURES={FEATURES.CONTROLLING: F.NEVER}):
            response = self.client.get(person.urls["detail"])
            self.assertContains(response, "Relaunch")
            self.assertNotContains(response, "Recent invoices")

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
            headers={
                "referer": person.urls["detail"],
                "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            },
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


class ArchiveContactsTest(TestCase):
    def test_unused_contacts(self):
        """People unused for five years and only in archived groups are
        archived"""
        cutoff = timezone.now() + dt.timedelta(days=1)  # Every change is older
        organization = factories.OrganizationFactory.create()
        unused = factories.PersonFactory.create(organization=organization)
        in_group = factories.PersonFactory.create(organization=organization)
        group = Group.objects.create(title="Newsletter 2015")
        in_group.groups.add(group)
        contact = factories.ProjectFactory.create().contact
        user = factories.UserFactory.create()
        user.person = factories.PersonFactory.create()
        user.save()

        def unused_people():
            return set(tasks.unused_people(cutoff))

        self.assertEqual(unused_people(), {unused})
        self.assertEqual(set(tasks.unused_organizations(cutoff)), set())
        self.assertNotIn(contact, unused_people())

        group.is_archived = True
        group.save()
        self.assertEqual(unused_people(), {unused, in_group})

        # Recent changes keep contacts
        self.assertEqual(
            set(tasks.unused_people(timezone.now() - dt.timedelta(days=1))), set()
        )

        # The audit log shows the contacts as changed long ago
        LoggedAction.objects.update(
            created_at=timezone.now() - dt.timedelta(days=6 * 365)
        )
        tasks.archive_unused_contacts()
        unused.refresh_from_db()
        organization.refresh_from_db()
        self.assertTrue(unused.is_archived)
        # Organizations whose people are all archived are archived too
        self.assertTrue(organization.is_archived)
        self.assertFalse(Person.objects.get(pk=contact.pk).is_archived)
        self.assertFalse(Person.objects.get(pk=user.person.pk).is_archived)

    def test_groups_keep_people_only(self):
        """Groups don't keep organizations without active people"""
        cutoff = timezone.now() + dt.timedelta(days=1)  # Every change is older
        group = Group.objects.create(title="Industry")
        organization = factories.OrganizationFactory.create()
        organization.groups.add(group)
        self.assertEqual(set(tasks.unused_organizations(cutoff)), {organization})

    @override_settings(BREVO_WEBHOOK_URL="https://brevo.example.com/hook")
    def test_brevo_person_without_logged_insert(self):
        """People whose creation isn't in the audit log (anymore) are sent too"""
        person = factories.PersonFactory.create()
        LoggedAction.objects.filter(
            table_name=Person._meta.db_table, action="I"
        ).delete()
        person.emailaddresses.create(email="test@example.com")

        with mock.patch("workbench.contacts.tasks.api.post") as post:
            tasks.upload_contacts_to_brevo()

        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs["json"]["email"], "test@example.com")
        self.assertEqual(post.call_args.kwargs["json"]["created_at"], "")

    def test_all_relations_known(self):
        """New relations to contacts keep them active until it's decided
        which of their objects count as recent use"""
        recent = tasks._recent(timezone.now())
        for model in [Person, Organization]:
            for field in tasks._reverse_relations(model):
                with self.subTest(model=model, field=field):
                    self.assertIn(field.related_model, recent)


class GroupsTest(TestCase):
    def test_groups(self):
        """Groups are managed in Workbench, archived ones aren't offered"""
        user = factories.UserFactory.create()
        self.client.force_login(user)
        response = self.client.post(
            Group.urls["create"],
            {"modal-title": "Newsletter"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 201)
        group = Group.objects.get()
        person = factories.PersonFactory.create()
        person.groups.add(group)

        response = self.client.get(Group.urls["list"])
        self.assertContains(response, "Newsletter")
        self.assertContains(response, "1 person")

        # Sorted by title, counting doesn't change that
        Group.objects.create(title="b-list")
        Group.objects.create(title="Alumni")
        content = self.client.get(Group.urls["list"]).content.decode()
        self.assertLess(content.index("Alumni"), content.index("b-list"))
        self.assertLess(content.index("b-list"), content.index("Newsletter"))

        response = self.client.post(
            group.urls["update"],
            {"modal-title": "Newsletter 2015", "modal-is_archived": "on"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)
        link = f'href="{group.get_absolute_url()}"'
        self.assertNotContains(self.client.get(Group.urls["list"]), link)
        self.assertContains(self.client.get(Group.urls["list"] + "?s=archived"), link)

        # Archived groups are offered only to contacts already in them
        other = factories.PersonFactory.create()
        response = self.client.get(other.urls["update"])
        self.assertNotContains(response, "Newsletter 2015")
        response = self.client.get(person.urls["update"])
        self.assertContains(response, "Newsletter 2015")

    def test_group_filter(self):
        """Archived groups are offered separately in the filters"""
        self.client.force_login(factories.UserFactory.create())
        Group.objects.create(title="Team")
        Group.objects.create(title="Newsletter 2015", is_archived=True)
        for url in ["/contacts/people/", "/contacts/organizations/"]:
            with self.subTest(url=url):
                content = self.client.get(url).content.decode()
                self.assertLess(
                    content.index('<optgroup label="Active">'),
                    content.index(">Team</option>"),
                )
                self.assertLess(
                    content.index('<optgroup label="Archived">'),
                    content.index(">Newsletter 2015</option>"),
                )

    def test_no_group_filter(self):
        """The no group filter lists active people without an active group"""
        self.client.force_login(factories.UserFactory.create())
        archived = Group.objects.create(title="Newsletter 2015", is_archived=True)
        grouped = factories.PersonFactory.create(given_name="Grouped")
        grouped.groups.set([Group.objects.create(title="Team")])
        factories.PersonFactory.create(given_name="Groupless")
        factories.PersonFactory.create(given_name="Formerly").groups.set([archived])
        factories.PersonFactory.create(given_name="Gone", is_archived=True)

        response = self.client.get("/contacts/people/?s=no-group")
        self.assertNotContains(response, "Grouped Nachname")
        self.assertContains(response, "Groupless Nachname")
        self.assertContains(response, "Formerly Nachname")
        self.assertNotContains(response, "Gone Nachname")

    def test_missing_postal_address(self):
        """The defined search finds people without a complete postal address,
        e.g. the members of a group for a mailing"""
        self.client.force_login(factories.UserFactory.create())
        complete = factories.PersonFactory.create(given_name="Complete")
        complete.postaladdresses.create(
            street="Hauptstrasse", house_number="1", postal_code="8000", city="Zürich"
        )
        incomplete = factories.PersonFactory.create(given_name="Incomplete")
        incomplete.postaladdresses.create(street="Hauptstrasse", city="Zürich")
        override = factories.PersonFactory.create(given_name="Override")
        override.postaladdresses.create(
            street="-", city="-", postal_address_override="Postfach\n8000 Zürich"
        )
        factories.PersonFactory.create(given_name="Missing")
        factories.PersonFactory.create(given_name="Gone", is_archived=True)

        response = self.client.get("/contacts/people/?s=missing-postal-address")
        self.assertNotContains(response, "Complete Nachname")
        self.assertContains(response, "Incomplete Nachname")
        self.assertNotContains(response, "Override Nachname")
        self.assertContains(response, "Missing Nachname")
        self.assertNotContains(response, "Gone Nachname")

        data = self.client.get(
            "/api/contacts/people/", {"missing_postal_address": "true"}
        ).json()
        self.assertEqual(
            {p["given_name"] for p in data["items"]}, {"Incomplete", "Missing"}
        )

    def test_member_counts(self):
        """People and organizations are counted independently of each other"""
        group = Group.objects.create(title="Newsletter")
        Group.objects.create(title="Empty")
        for archived in [False, False, True]:
            factories.PersonFactory.create(is_archived=archived).groups.add(group)
        for archived in [False, True, True, True]:
            factories.OrganizationFactory.create(is_archived=archived).groups.add(group)

        form = GroupSearchForm({}, request=RequestFactory().get("/"))
        self.assertTrue(form.is_valid())
        counts = {
            g.title: (
                g.people_count,
                g.organizations_count,
                g.archived_people_count,
                g.archived_organizations_count,
            )
            for g in form.filter(Group.objects.all())
        }
        self.assertEqual(counts, {"Newsletter": (2, 1, 1, 3), "Empty": (0, 0, 0, 0)})

    def test_archived_members(self):
        """People see that a group contains archived contacts, but not which"""
        self.client.force_login(factories.UserFactory.create())
        group = Group.objects.create(title="Newsletter")
        active = factories.PersonFactory.create(family_name="Active")
        archived = factories.PersonFactory.create(family_name="Gone", is_archived=True)
        active.groups.add(group)
        archived.groups.add(group)

        content = self.client.get(Group.urls["list"]).content.decode()
        self.assertIn("1 person", content)
        self.assertIn("1 archived", content)
        self.assertIn(f'href="/contacts/organizations/?g={group.pk}"', content)

        response = self.client.get(group.get_absolute_url())
        self.assertContains(response, "This group also contains 1 archived contact.")
        self.assertNotContains(response, "Gone")
        # Asking for all contacts shows them, the note isn't needed then
        response = self.client.get(group.get_absolute_url() + "&s=all")
        self.assertNotContains(response, "archived contact")


class OrganizationGroupsTest(TestCase):
    """Groups which apply to organizations (e.g. industries) are joined by
    people through their organization"""

    def setUp(self):
        deactivate_all()
        self.industry = Group.objects.create(
            title="Industry", applies_to_organizations=True
        )
        self.newsletter = Group.objects.create(title="Newsletter")
        self.organization = factories.OrganizationFactory.create()
        self.organization.groups.add(self.industry)
        self.person = factories.PersonFactory.create(organization=self.organization)
        self.person.groups.add(self.newsletter)

    def test_flag_moves_memberships(self):
        """Applying a group to organizations moves the memberships of people
        with an organization to their organization"""
        group = Group.objects.create(title="Film")
        self.person.groups.add(group)
        alone = factories.PersonFactory.create()
        alone.groups.add(group)

        self.client.force_login(self.person.primary_contact)
        response = self.client.post(
            group.urls["update"],
            {"modal-title": "Film", "modal-applies_to_organizations": "on"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(set(self.person.groups.all()), {self.newsletter})
        self.assertEqual(set(self.organization.groups.all()), {self.industry, group})
        self.assertEqual(set(alone.groups.all()), {group})

    def test_person_form(self):
        """The person form shows the groups of the organization too, changes
        to groups which apply to organizations go to the organization"""
        film = Group.objects.create(title="Film", applies_to_organizations=True)
        self.client.force_login(self.person.primary_contact)
        response = self.client.get(self.person.urls["update"])
        self.assertEqual(
            set(response.context["form"].initial["groups"]),
            {self.industry.pk, self.newsletter.pk},
        )

        response = self.client.post(
            self.person.urls["update"],
            person_to_dict(
                self.person,
                salutation="Dear John",
                groups=[film.pk, self.newsletter.pk],
            ),
        )
        self.assertRedirects(response, self.person.urls["detail"])
        self.assertEqual(set(self.person.groups.all()), {self.newsletter})
        self.assertEqual(set(self.organization.groups.all()), {film})

    def test_person_without_organization(self):
        """People without an organization are in such groups themselves"""
        person = factories.PersonFactory.create()
        self.client.force_login(person.primary_contact)
        response = self.client.post(
            person.urls["update"],
            person_to_dict(person, salutation="Dear John", groups=[self.industry.pk]),
        )
        self.assertRedirects(response, person.urls["detail"])
        self.assertEqual(set(person.groups.all()), {self.industry})

    def test_people_list(self):
        """The people list finds and shows people through their organization"""
        self.client.force_login(self.person.primary_contact)
        response = self.client.get(f"/contacts/people/?g={self.industry.pk}")
        self.assertEqual(list(response.context["object_list"]), [self.person])
        self.assertContains(response, ">Industry</a>")

        # Groups which don't apply to organizations don't pass to people
        self.organization.groups.add(self.newsletter)
        other = factories.PersonFactory.create(organization=self.organization)
        response = self.client.get(f"/contacts/people/?g={self.newsletter.pk}")
        self.assertEqual(list(response.context["object_list"]), [self.person])

        response = self.client.get("/contacts/people/?s=no-group")
        self.assertEqual(list(response.context["object_list"]), [])
        self.organization.groups.remove(self.industry)
        response = self.client.get("/contacts/people/?s=no-group")
        self.assertEqual(list(response.context["object_list"]), [other])

    def test_member_counts(self):
        """People are counted through their organization"""
        factories.PersonFactory.create(organization=self.organization)
        self.industry.person_set.add(factories.PersonFactory.create())
        form = GroupSearchForm({}, request=RequestFactory().get("/"))
        self.assertTrue(form.is_valid())
        counts = {g.title: g.people_count for g in form.filter(Group.objects.all())}
        self.assertEqual(counts, {"Industry": 3, "Newsletter": 1})

    def test_detail_and_api(self):
        """The person's detail page and the API list the organization's groups"""
        self.client.force_login(self.person.primary_contact)
        self.assertContains(self.client.get(self.person.urls["detail"]), "Industry")
        response = self.client.get(f"/api/contacts/people/{self.person.pk}/")
        self.assertEqual(response.json()["groups"], ["Industry", "Newsletter"])

    def test_archival(self):
        """Groups which apply to organizations keep their people"""
        cutoff = timezone.now() + dt.timedelta(days=1)  # Every change is older
        self.person.groups.clear()
        self.assertEqual(set(tasks.unused_people(cutoff)), set())
