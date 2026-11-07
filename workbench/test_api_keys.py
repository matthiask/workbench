from django.test import TestCase

from workbench import factories
from workbench.api_keys import FIELDS, KEYS, key


class APIKeysTest(TestCase):
    def test_bijective(self):
        """Every stored value has exactly one key and every key one value"""
        self.assertEqual(set(KEYS), set(FIELDS))
        for name, keys in KEYS.items():
            with self.subTest(name=name):
                model, field = FIELDS[name]
                values = [
                    value for value, _label in model._meta.get_field(field).choices
                ]
                # All values of the field, no others
                self.assertEqual(sorted(keys.values()), sorted(values))
                # No value twice, so the keys are a bijection
                self.assertEqual(len(set(keys.values())), len(keys))
                for k, value in keys.items():
                    self.assertEqual(key(name, value), k)
                # Keys are stable identifiers
                for k in keys:
                    self.assertRegex(k, r"^[a-z_]+$")

    def test_choices(self):
        """The keys are listed with their labels in their natural order"""
        self.client.force_login(factories.UserFactory.create(language="de"))
        data = self.client.get("/api/choices/").json()
        self.assertEqual(set(data), set(KEYS))
        self.assertEqual(
            [choice["key"] for choice in data["offer_status"]],
            [
                "in_preparation",
                "service_group",
                "offered",
                "accepted",
                "declined",
                "discarded",
            ],
        )
        self.assertEqual(
            data["deal_probability"][0], {"key": "unknown", "label": "unbekannt"}
        )

    def test_outputs(self):
        """Outputs carry the keys and localized labels"""
        user = factories.UserFactory.create(language="de")
        self.client.force_login(user)
        deal = factories.DealFactory.create(owned_by=user)
        offer = factories.OfferFactory.create()
        invoice = factories.InvoiceFactory.create()

        data = self.client.get(f"/api/deals/{deal.pk}/").json()
        self.assertEqual((data["status"], data["status_label"]), ("open", "Offen"))
        self.assertEqual(data["probability"], key("deal_probability", deal.probability))

        data = self.client.get(f"/api/offers/{offer.pk}/").json()
        self.assertEqual(
            (data["status"], data["status_label"]),
            ("in_preparation", "In Vorbereitung"),
        )

        data = self.client.get(f"/api/invoices/{invoice.pk}/").json()
        self.assertEqual(
            (data["status"], data["status_label"]),
            ("in_preparation", "In Vorbereitung"),
        )
