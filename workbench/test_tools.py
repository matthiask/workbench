from decimal import Decimal

from django import forms
from django.db.models import ProtectedError
from django.test import TestCase

from workbench import factories
from workbench.awt.models import Year  # any tools.Model()
from workbench.contacts.models import Organization
from workbench.projects.models import Project
from workbench.tools.forms import Autocomplete
from workbench.tools.models import ModelWithTotal
from workbench.tools.testing import messages


class ToolsTest(TestCase):
    def test_model(self):
        self.assertEqual(Year().code, "")
        self.assertEqual(Year(pk=3).code, "00003")
        self.assertEqual(Year().pretty_status, "")
        self.assertEqual(
            Year(year=2012).snippet(),
            '\n<a href="/report/annual-working-time/?year=2012">\n  Jahr: 2012\n</a>\n',
        )

    def test_invalid_autocomplete(self):
        class ProjectForm(forms.ModelForm):
            class Meta:
                model = Project
                fields = ["customer"]
                widgets = {"customer": Autocomplete(model=Organization)}

        form = ProjectForm(initial={"customer": "test"})
        self.assertIn('value=""', str(form))

    def test_model_with_total(self):
        m = ModelWithTotal(
            subtotal=Decimal("20"), discount=Decimal("5"), tax_rate=Decimal("8.0")
        )
        m._calculate_total()

        self.assertAlmostEqual(m._round_5cents(Decimal("1.02")), Decimal("1.00"))
        self.assertAlmostEqual(m._round_5cents(Decimal("1.03")), Decimal("1.05"))
        self.assertAlmostEqual(m.tax_amount, Decimal("1.20"))
        self.assertAlmostEqual(m.total_excl_tax, Decimal("15"))
        self.assertAlmostEqual(m.total, Decimal("16.20"))

        self.assertEqual(m.pretty_total_excl, "15.00 exkl. MwSt. (5.00 Rabatt)")

    def test_create_absence_redirect(self):
        self.client.force_login(factories.UserFactory.create())
        response = self.client.get("/absences/create/")
        self.assertRedirects(response, "/absences/")

    def test_deletion(self):
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
                "Kann '{}' wegen Abhängigkeiten nicht löschen (Any service: Bla)."
                "".format(project)
            ],
        )
