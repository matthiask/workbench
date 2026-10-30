import datetime as dt
from decimal import Decimal

from django import forms
from django.db.models import ProtectedError
from django.test import TestCase
from time_machine import travel

from workbench import factories
from workbench.awt.models import Year  # any tools.Model()
from workbench.contacts.models import Organization
from workbench.projects.models import Project
from workbench.tools import formats
from workbench.tools.charts import bar_chart, nice_step
from workbench.tools.forms import Autocomplete
from workbench.tools.models import CalculationModel
from workbench.tools.testing import messages
from workbench.tools.validation import is_title_specific, last_month_range, month_range


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
        m = CalculationModel(
            subtotal=Decimal(20), discount=Decimal(5), tax_rate=Decimal("8.0")
        )
        m._calculate_total()

        self.assertAlmostEqual(m._round_5cents(Decimal("1.02")), Decimal("1.00"))
        self.assertAlmostEqual(m._round_5cents(Decimal("1.03")), Decimal("1.05"))
        self.assertAlmostEqual(m.tax_amount, Decimal("1.20"))
        self.assertAlmostEqual(m.total_excl_tax, Decimal(15))
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
                (
                    f"Cannot delete '{project}' because of related objects (Any service: Bla)."
                    ""
                )
            ],
        )

    def test_formats_hours(self):
        """Number formatting"""
        for value, result in [
            (Decimal("42.22"), "42.2h"),
            (Decimal("42.27"), "42.3h"),
            (Decimal(3), "3.0h"),
            (Decimal(-123), "-123.0h"),
            (Decimal("0.003"), "0.0h"),
            (Decimal("-0.003"), "0.0h"),
            (Decimal(12345), "12’345.0h"),
            (None, "0.0h"),
        ]:
            with self.subTest(value=value, result=result):
                self.assertEqual(formats.hours(value), result)

    @travel("2024-03-15")
    def test_month_range(self):
        """Month ranges include the first and last day of the month"""
        self.assertEqual(month_range(), [dt.date(2024, 3, 1), dt.date(2024, 3, 31)])
        self.assertEqual(
            month_range(dt.date(2024, 2, 29)),
            [dt.date(2024, 2, 1), dt.date(2024, 2, 29)],
        )
        self.assertEqual(
            month_range(dt.date(2023, 12, 31)),
            [dt.date(2023, 12, 1), dt.date(2023, 12, 31)],
        )
        self.assertEqual(
            last_month_range(), [dt.date(2024, 2, 1), dt.date(2024, 2, 29)]
        )
        with travel("2024-01-31"):
            self.assertEqual(
                last_month_range(), [dt.date(2023, 12, 1), dt.date(2023, 12, 31)]
            )

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

    def test_nice_step(self):
        """Axis steps are round numbers"""
        for maximum, step in [(1, "0.25"), (7, "2"), (100, "25"), (93_000, "25000")]:
            with self.subTest(maximum=maximum):
                self.assertEqual(nice_step(maximum), Decimal(step))

    def test_bar_chart(self):
        """Bars stack positive and negative values separately, lines skip
        missing values and every column gets a tooltip"""
        chart = bar_chart(
            ["A", "B", "C"],
            bars=[
                {"label": "One", "values": [1, -1, 0], "color": "wb-series-1"},
                {"label": "Two", "values": [2, -2, 3], "color": "wb-series-2"},
            ],
            lines=[{"label": "Goal", "values": [4, None, 4], "color": "x"}],
            fmt=formats.hours,
        )
        self.assertEqual(
            [tick["label"] for tick in chart["y_ticks"]],
            ["-2.0h", "0.0h", "2.0h", "4.0h"],
        )
        # Two bars of the first series, the zero is left out
        self.assertEqual(chart["bars"][0]["path"].count("M"), 2)
        self.assertEqual(chart["lines"][0]["path"].count("L"), 1)
        self.assertEqual(chart["columns"][1]["title"], "B\nOne: -1.0h\nTwo: -2.0h")
        self.assertEqual(
            [item["kind"] for item in chart["legend"]], ["bar", "bar", "line"]
        )

        self.assertEqual(bar_chart([])["y_ticks"][-1]["label"], "0.25")
