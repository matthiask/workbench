from collections import Counter
from datetime import date

from workbench.accounts.models import User

from .models import App


def run(year=None):
    for app in App.objects.all():
        run_app(app, year=date.today().year if year is None else year)


def run_app(app, year):
    print(f"{app}")
    counts = Counter(
        app.days.filter(day__year=year).values_list("handled_by", flat=True)
    )
    presences = dict(app.presences.filter(year=year).values_list("user", "percentage"))

    users = (
        User.objects.filter(id__in=set(counts.keys()) | set(presences))
        | app.users.all()
    ).distinct()
    presences_sum = sum(presences.values())
    counts_sum = sum(
        (
            count
            for user_id, count in counts.items()
            if user_id in presences or user_id is None
        ),
        0,
    )

    with_presence = []
    without_presence = []

    for user in users:
        if user.id in presences:
            presence = presences[user.id]
            reached = presence / presences_sum * counts_sum

            with_presence.append(
                "{:>20.20}: {:>3}%, Soll {:>3}, Ist {:>3}, Erreichung {}%".format(
                    user.get_full_name(),
                    presence,
                    round(reached),
                    counts[user.id],
                    round(100 * counts[user.id] / reached) if reached else "-",
                )
            )
        else:
            without_presence.append(
                f"{user.get_full_name():>20.20}:           {-counts[user.id]:>4} Tage"
            )

    print(f"Gesamthaft                       {sum(counts.values())} Tage")
    print("\n".join(without_presence))
    print()
    print(f"Zu verteilen auf      {presences_sum:>3}%:      {counts_sum:>3} Tage")
    print("\n".join(with_presence))
