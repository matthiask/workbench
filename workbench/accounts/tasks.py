import datetime as dt
import random

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from authlib.email import render_to_mail

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User


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


def coffee_invites():
    year, week, weekday = dt.date.today().isocalendar()
    if weekday != 1 or week % 2 == 0:
        return
    # It is a monday in an odd ISO calendar week
    users = list(
        User.objects.active().order_by("?").filter(_features__overlap=[FEATURES.COFFEE])
    )

    if len(users) < 2:
        # :-(
        return

    while users:
        if len(users) == 3:
            group, users = users, []
        else:
            group, users = users[:2], users[2:]

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
