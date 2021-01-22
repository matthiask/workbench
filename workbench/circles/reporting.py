from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum
from django.utils.translation import gettext as _

from workbench.accounts.models import User
from workbench.circles.models import Circle, Role
from workbench.logbook.models import LoggedHours
from workbench.tools.formats import Z1


def hours_by_circle(date_range, *, users=None):
    queryset = LoggedHours.objects.order_by().filter(rendered_on__range=date_range)
    if users:
        queryset = queryset.filter(rendered_by__in=users)

    queryset = queryset.values("service__role", "rendered_by").annotate(Sum("hours"))
    seen_users = set()

    hours_by_role = defaultdict(lambda: defaultdict(Decimal))
    hours_by_circle = defaultdict(lambda: defaultdict(Decimal))

    roles_to_circle = {role.id: role.circle_id for role in Role.objects.all()}

    for row in queryset:
        hours_by_role[row["service__role"]][row["rendered_by"]] = row["hours__sum"]
        hours_by_circle[roles_to_circle.get(row["service__role"])][
            row["rendered_by"]
        ] += row["hours__sum"]
        seen_users.add(row["rendered_by"])

    users = list(User.objects.filter(id__in=seen_users))

    circles = [
        {
            "users": users,
            "circle": None,
            "by_user": [(user, hours_by_circle[None][user.id]) for user in users],
            "total": sum(hours_by_circle[None].values(), Decimal()),
        }
    ]
    for circle in Circle.objects.prefetch_related("roles"):
        row = {
            "circle": circle,
            "roles": [],
            "by_user": [(user, hours_by_circle[circle.id][user.id]) for user in users],
            "total": sum(hours_by_circle[circle.id].values(), Decimal()),
        }

        for role in circle.roles.all():
            role_total = sum(hours_by_role[role.id].values(), Decimal())
            if role_total:
                row["roles"].append(
                    {
                        "role": role,
                        "by_user": [
                            (user, hours_by_role[role.id][user.id]) for user in users
                        ],
                        "total": role_total,
                    }
                )
        if row["total"]:
            circles.append(row)
    return {
        "circles": circles,
        "total_hours": sum((circle["total"] for circle in circles), Decimal()),
    }


def hours_per_work_category(date_range, *, users=None):
    queryset = LoggedHours.objects.order_by().filter(rendered_on__range=date_range)
    if users:
        queryset = queryset.filter(rendered_by__in=users)

    queryset = queryset.values("service__role__work_category", "rendered_by").annotate(
        Sum("hours")
    )
    seen_users = set()

    by_user_and_category = defaultdict(lambda: defaultdict(Decimal))
    by_category = defaultdict(Decimal)

    for row in queryset:
        by_user_and_category[row["rendered_by"]][
            row["service__role__work_category"] or None
        ] = row["hours__sum"]
        by_category[row["service__role__work_category"] or None] += row["hours__sum"]
        seen_users.add(row["rendered_by"])

    users = [
        (
            user,
            {
                "total": sum(by_user_and_category[user.id].values(), Z1),
                "per_category": [
                    (row[0], by_user_and_category[user.id][row[0]])
                    for row in Role.CATEGORIES
                ],
                "undefined": by_user_and_category[user.id][None],
            },
        )
        for user in User.objects.filter(id__in=seen_users)
    ]
    return {
        "categories": Role.CATEGORIES,
        "users": users,
        "chart": [
            {
                "label": title,
                "hours": [
                    100 * by_user_and_category[user.id][name] / user_stats["total"]
                    for user, user_stats in users
                ],
            }
            for name, title, description in Role.CATEGORIES
        ]
        + [
            {
                "label": _("Undefined"),
                "hours": [
                    100 * by_user_and_category[user.id][None] / user_stats["total"]
                    for user, user_stats in users
                ],
            }
        ],
        "summary": {
            "total": sum(by_category.values(), Z1),
            "per_category": [(row[0], by_category[row[0]]) for row in Role.CATEGORIES],
            "undefined": by_category[None],
        },
    }
