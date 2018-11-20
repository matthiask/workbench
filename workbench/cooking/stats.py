from collections import Counter

from workbench.accounts.models import User

from .models import Day, Presence


def run(year=2019):
    counts = Counter(
        Day.objects.filter(day__year=year).values_list("handled_by", flat=True)
    )
    presences = dict(
        Presence.objects.filter(year=year).values_list("user", "percentage")
    )

    users = User.objects.filter(id__in=set(counts.keys()) | set(presences))
    presences_sum = sum(presences.values())
    counts_sum = sum(
        (
            count
            for user_id, count in counts.items()
            if user_id in presences or user_id is None
        ),
        0,
    )

    print(
        "{} Tage gesamt, davon {} zu verteilen auf {}% Präsenz".format(
            sum(counts.values()), counts_sum, presences_sum
        )
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
                "{:>20.20}: Kein Soll, Ist {:>3}".format(
                    user.get_full_name(), counts[user.id]
                )
            )

    print("{}\n\n{}".format("\n".join(with_presence), "\n".join(without_presence)))
