from decimal import Decimal

from django import forms
from django.db.models import ProtectedError
from django.test import TestCase

from workbench import factories
from workbench.awt.models import Year  # any tools.Model()
from workbench.contacts.models import Organization
from workbench.projects.models import Project
from workbench.tools import formats
from workbench.tools.forms import Autocomplete
from workbench.tools.models import ModelWithTotal
from workbench.tools.testing import messages
from workbench.tools.validation import is_title_specific


class ToolsTest(TestCase):
    def test_model(self):
        """Shared methods of tools.models.Model work"""
        self.assertEqual(Year().code, "")
        self.assertEqual(Year(pk=3).code, "00003")
        self.assertEqual(Year().pretty_status, "")

    def test_invalid_autocomplete(self):
        """Invalid initial values for the Autocomplete widget are ignored"""

        class ProjectForm(forms.ModelForm):
            class Meta:
                model = Project
                fields = ["customer"]
                widgets = {"customer": Autocomplete(model=Organization)}

        form = ProjectForm(initial={"customer": "test"})
        self.assertIn('value=""', str(form))

    def test_model_with_total(self):
        """The calculation of totals excl. and incl. tax work"""
        m = ModelWithTotal(
            subtotal=Decimal("20"), discount=Decimal("5"), tax_rate=Decimal("8.0")
        )
        m._calculate_total()

        self.assertAlmostEqual(m._round_5cents(Decimal("1.02")), Decimal("1.00"))
        self.assertAlmostEqual(m._round_5cents(Decimal("1.03")), Decimal("1.05"))
        self.assertAlmostEqual(m.tax_amount, Decimal("1.20"))
        self.assertAlmostEqual(m.total_excl_tax, Decimal("15"))
        self.assertAlmostEqual(m.total, Decimal("16.20"))

        self.assertEqual(m.pretty_total_excl, "15.00 excl. tax (5.00 discount)")

    def test_create_absence_redirect(self):
        """The create view uses the get_redirect_url of models"""
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/absences/create/")
        self.assertRedirects(response, "/absences/")

    def test_deletion(self):
        """Related objects are checked automatically when attempting deletion"""
        hours = factories.LoggedHoursFactory.create(description="Bla")
        project = hours.service.project

        with self.assertRaises(ProtectedError):
            project.delete()

        self.client.force_login(hours.rendered_by)
        response = self.client.get(project.urls["delete"])
        self.assertRedirects(response, project.urls["detail"])
        self.assertEqual(
            messages(response),
            [
                "Cannot delete '{}' because of related objects (Any service: Bla)."
                "".format(project)
            ],
        )

    def test_formats_hours(self):
        """Number formatting"""
        for value, result in [
            (Decimal("42.22"), "42.2h"),
            (Decimal("42.27"), "42.3h"),
            (Decimal("3"), "3.0h"),
            (Decimal("-123"), "-123.0h"),
            (Decimal("0.003"), "0.0h"),
            (Decimal("-0.003"), "0.0h"),
            (Decimal("12345"), "12’345.0h"),
            (None, "0.0h"),
        ]:
            with self.subTest(value=value, result=result):
                self.assertEqual(formats.hours(value), result)

    def test_is_title_specific(self):
        """is_title_specific tests"""
        self.assertTrue(is_title_specific("Implementation Kontaktformular"))
        self.assertFalse(is_title_specific("Programmierung allgemein"))
        self.assertTrue(
            is_title_specific("Analyse der Storyboards und allgemeine Anforderungen")
        )

    def test_formats_minutes_and_hours(self):
        """Duration formatting"""
        for value, result in [
            (0, "0 minutes"),
            (60, "1 minute"),
            (3600, "1 hour 0 minutes"),
            (7261, "2 hours 1 minute"),
        ]:
            with self.subTest(value=value, result=result):
                self.assertEqual(formats.hours_and_minutes(value), result)
