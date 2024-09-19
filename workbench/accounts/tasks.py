import datetime as dt
import math
import random
from itertools import chain

from authlib.email import render_to_mail
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.features import FEATURES
from workbench.accounts.models import CoffeePairings, User


CANDIDATES = 20
WISHES = [
    _("I hope you’ll enjoy it :-)"),
    _("But even a bad cup of coffee is better than no coffee at all. – David Lynch"),
    _("You can’t buy happiness but you can buy coffee and that’s pretty close."),
    _("What goes best with a cup of coffee? Another cup. – Henry Rollins"),
    _("Life is too short for bad coffee."),
    _("May your coffee be strong and your monday be short."),
    _("Time to drink some coffee."),
    _("Drink coffee. Do stupid things faster with more energy."),
]


def generate_pairings(users):
    randomized = random.sample(users, len(users))

    while randomized:
        if len(randomized) == 3:
            yield (
                randomized,
                [
                    tuple(sorted((randomized[0].id, randomized[1].id))),
                    tuple(sorted((randomized[0].id, randomized[2].id))),
                    tuple(sorted((randomized[1].id, randomized[2].id))),
                ],
            )
            break

        else:
            group, randomized = randomized[:2], randomized[2:]
            yield group, [tuple(sorted((group[0].id, group[1].id)))]


def rating(pairing, previous):
    """The lower the rating value is the better"""
    current = set(chain.from_iterable(pair[1] for pair in pairing))
    overlaps = current & set(previous)
    if overlaps:
        return sum(math.pow(0.97, previous[overlap] / 86400) for overlap in overlaps)
    return 0.0


def coffee_invites():
    _year, week, weekday = dt.date.today().isocalendar()
    if weekday != 1 or week % 2 == 0:
        return
    # It is a monday in an odd ISO calendar week
    users = [user for user in User.objects.active() if user.features[FEATURES.COFFEE]]

    if len(users) < 2:
        # :-(
        return

    now = timezone.now()
    previous = {
        tuple(sorted(pairing.users)): (now - pairing.created_at).total_seconds()
        for pairing in CoffeePairings.objects.order_by("created_at")
    }

    # Generate $CANDIDATES candidate pairings
    candidates = [list(generate_pairings(users)) for _ in range(CANDIDATES)]

    # Rate the candidates
    rated_candidates = sorted(
        (rating(candidate, previous), candidate) for candidate in candidates
    )

    # Select the pairing with the best (lowest) rating
    best_pairing = rated_candidates[0][1]

    # from pprint import pprint
    # pprint(previous)
    # pprint(rated_candidates)

    for group, pairs in best_pairing:
        for pair in pairs:
            CoffeePairings.objects.create(users=pair)
        render_to_mail(
            "accounts/coffee_mail",
            {
                "group": group,
                "names": ", ".join(user.get_full_name() for user in group),
                "wish": random.choice(WISHES),
                "WORKBENCH": settings.WORKBENCH,
            },
            to=[user.email for user in group],
            reply_to=[user.email for user in group],
        ).send()
