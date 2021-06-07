import datetime as dt
import random
from itertools import chain

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from authlib.email import render_to_mail

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
            yield randomized, [
                tuple(sorted((randomized[0].id, randomized[1].id))),
                tuple(sorted((randomized[0].id, randomized[2].id))),
                tuple(sorted((randomized[1].id, randomized[2].id))),
            ]
            break

        else:
            group, randomized = randomized[:2], randomized[2:]
            yield group, [tuple(sorted((group[0].id, group[1].id)))]


def overlap(pairing, previous):
    current = set(chain.from_iterable(pair[1] for pair in pairing))
    return len(current & previous)


def coffee_invites():
    year, week, weekday = dt.date.today().isocalendar()
    if weekday != 1 or week % 2 == 0:
        return
    # It is a monday in an odd ISO calendar week
    users = list(User.objects.active().filter(_features__overlap=[FEATURES.COFFEE]))

    if len(users) < 2:
        # :-(
        return

    previous = {
        tuple(sorted(pairing.users))
        for pairing in CoffeePairings.objects.filter(
            created_at__gt=timezone.now() - dt.timedelta(days=14 * len(users) // 2)
        )
    }

    # Generate $CANDIDATES candidate pairings
    candidates = [list(generate_pairings(users)) for _ in range(CANDIDATES)]

    # Count how many pairs already occurred in the relevant comparison period
    rated_candidates = sorted(
        (overlap(candidate, previous), candidate) for candidate in candidates
    )

    for group, pairs in rated_candidates[0][1]:
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
