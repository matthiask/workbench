from django.core import mail
from django.test import TestCase
from time_machine import travel

from workbench import factories
from workbench.accounts.features import FEATURES
from workbench.accounts.tasks import coffee_invites


class CoffeeTest(TestCase):
    @travel("2021-05-10")
    def test_coffee_invites(self):
        """Coffee invites"""

        # No participants
        factories.UserFactory.create()
        coffee_invites()
        self.assertEqual(len(mail.outbox), 0)

        factories.UserFactory.create()
        coffee_invites()
        self.assertEqual(len(mail.outbox), 0)

        # Only one participant :-(
        factories.UserFactory.create(_features=[FEATURES.COFFEE])
        coffee_invites()
        self.assertEqual(len(mail.outbox), 0)

        # One match!
        factories.UserFactory.create(_features=[FEATURES.COFFEE])
        coffee_invites()
        self.assertEqual(len(mail.outbox), 1)

        # One match! (three participants)
        factories.UserFactory.create(_features=[FEATURES.COFFEE])
        coffee_invites()
        self.assertEqual(len(mail.outbox), 2)

        # Two matches (four active participants)
        factories.UserFactory.create(is_active=False, _features=[FEATURES.COFFEE])
        factories.UserFactory.create(_features=[FEATURES.COFFEE])
        coffee_invites()
        self.assertEqual(len(mail.outbox), 4)

        # No match (wrong week)
        with travel("2021-05-17"):
            coffee_invites()
            self.assertEqual(len(mail.outbox), 4)
