from collections import Counter, defaultdict

from workbench.accounts.models import User

from .models import Day, Presence


def run(year=2019):
    users = User.objects.all()

    counts = Counter(
        Day.objects.filter(day__year=year).values_list("handled_by", flat=True)
    )
    counts_sum = sum(counts.values())
    presences = defaultdict(
        lambda: 100,
        Presence.objects.filter(year=year).values_list("user", "percentage"),
    )
    presences_sum = sum((presences[user.id] for user in users), 0)

    for user in users:
        reached = round(presences[user.id] / presences_sum * counts_sum)
        print(
            "{:>20.20}: {:>3}%, Soll {:>3}, Ist {:>3}, Erreichung {}%".format(
                user.get_full_name(),
                presences[user.id],
                reached,
                counts[user.id],
                round(100 * counts[user.id] / reached),
            )
        )
