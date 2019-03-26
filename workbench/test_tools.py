from django.test import TestCase

from workbench.awt.models import Year  # any tools.Model()


class ToolsTest(TestCase):
    def test_model(self):
        self.assertEqual(Year().code, "")
        self.assertEqual(Year(pk=3).code, "00003")
        self.assertEqual(Year().pretty_status, "")
        self.assertEqual(
            Year(year=2012).snippet(),
            '\n<a href="/report/annual-working-time/?year=2012">\n  Jahr: 2012\n</a>\n',
        )
