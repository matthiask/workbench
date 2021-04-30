import datetime as dt

from authlib.email import render_to_mail
from django.conf import settings

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User


def coffee_invites():
    year, week, weekday = dt.date.today().isocalendar()
    if weekday != 1 or week % 2 != 0:
        return

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
                "WORKBENCH": settings.WORKBENCH,
            },
            to=[user.email for user in group],
            reply_to=[user.email for user in group],
        ).send()
