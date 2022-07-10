from django.test import TestCase

from workbench.tools.pdf import get_debtor_address


DEBTOR_ADDRESES = [
    (
        """\
Hans Muster
Musterstrasse 42
1234 Musterstadt""",
        {
            "name": "Hans Muster",
            "line1": "Musterstrasse 42",
            "line2": "1234 Musterstadt",
            "country": "CH",
        },
    ),
    (
        """\
Musterfirma
Hans Muster
Musterstrasse 42
1234 Musterstadt""",
        {
            "name": "Musterfirma Hans Muster",
            "line1": "Musterstrasse 42",
            "line2": "1234 Musterstadt",
            "country": "CH",
        },
    ),
    (
        """\
Musterfirma
Hans Muster
Musterstrasse 42
Adresszusatz
1234 Musterstadt""",
        {
            "name": "Musterfirma Hans Muster Musterstrasse 42",
            "line1": "Adresszusatz",
            "line2": "1234 Musterstadt",
            "country": "CH",
        },
    ),
]


class QRTest(TestCase):
    def test_debtor_address(self):
        """The debtor address helper does what it should"""

        for have, want in DEBTOR_ADDRESES:
            with self.subTest(have=have, want=want):
                self.assertEqual(get_debtor_address(have), want)
