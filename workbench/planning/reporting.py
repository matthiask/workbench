import datetime as dt
from collections import defaultdict
from itertools import islice

from workbench.accounts.models import User
from workbench.invoices.utils import recurring
from workbench.planning.models import PlannedWork
from workbench.tools.formats import Z1, Z2, local_date_format
from workbench.tools.validation import monday


def planned_work(*, users=None):
    weeks = list(islice(recurring(monday(), "weekly"), 35))

    by_week = defaultdict(lambda: Z1)
    by_project_and_week = defaultdict(lambda: defaultdict(lambda: Z1))
    projects_offers = defaultdict(lambda: defaultdict(list))

    for pw in PlannedWork.objects.filter(weeks__overlap=weeks).select_related(
        "project__owned_by", "offer__project", "offer__owned_by"
    ):
        per_week = (pw.planned_hours / len(pw.weeks)).quantize(Z2)
        for week in pw.weeks:
            by_week[week] += per_week
            by_project_and_week[pw.project][week] += per_week

        projects_offers[pw.project][pw.offer].append(
            {
                "planned_work": {
                    "id": pw.id,
                    "title": pw.title,
                    "planned_hours": pw.planned_hours,
                    "update_url": pw.urls["update"],
                },
                "hours_per_week": [
                    per_week if week in pw.weeks else Z1 for week in weeks
                ],
            }
        )

    return {
        "weeks": [
            {
                "date_from": week,
                "date_until": week + dt.timedelta(days=6),
                "week": local_date_format(week, fmt="W"),
            }
            for week in weeks
        ],
        "projects_offers": sorted(
            [
                {
                    "project": {
                        "id": project.id,
                        "title": project.title,
                        "code": project.code,
                        "url": project.get_absolute_url(),
                    },
                    "by_week": [by_project_and_week[project][week] for week in weeks],
                    "offers": [
                        {
                            "offer": {
                                "id": offer.id,
                                "title": offer.title,
                                "code": offer.code,
                                "url": offer.get_absolute_url(),
                            }
                            if offer
                            else None,
                            "planned_works": planned_works,
                        }
                        for offer, planned_works in sorted(offers.items())
                    ],
                }
                for project, offers in projects_offers.items()
            ],
            key=lambda row: row["project"]["id"],  # FIXME sort by timeline
        ),
        "by_week": [by_week[week] for week in weeks],
    }


def test():  # pragma: no cover
    from pprint import pprint

    pprint(planned_work(users=[User.objects.get(pk=1)]))

    # pprint(accepted_deals([dt.date(2020, 1, 1), dt.date(2020, 3, 31)]))
