import random
from collections import Counter

from django.core import mail
from django.test import TestCase
from time_machine import travel

from workbench import factories
from workbench.accounts.features import FEATURES
from workbench.accounts.tasks import (
    OLD_WISHES,
    WISHES,
    coffee_invites,
    random_wish,
)


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

    def test_random_wish(self):
        """Wishes everyone has read many times appear less often"""
        random.seed(42)
        drawn = Counter(random_wish() for _ in range(5000))
        self.assertEqual(set(drawn), set(WISHES) | set(OLD_WISHES))
        self.assertLess(
            sum(drawn[wish] for wish in OLD_WISHES) / len(OLD_WISHES),
            sum(drawn[wish] for wish in WISHES) / len(WISHES) / 3,
        )
