from collections import defaultdict
from decimal import Decimal

from django.db.models import Sum

from workbench.accounts.models import User
from workbench.circles.models import Circle, Role
from workbench.logbook.models import LoggedHours


def logged_hours_by_circle(date_range, *, users=None):
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
            "by_user": [hours_by_circle[None][user.id] for user in users],
            "total": sum(hours_by_circle[None].values(), Decimal()),
        }
    ]
    for circle in Circle.objects.prefetch_related("roles"):
        row = {
            "circle": circle,
            "roles": [],
            "by_user": [hours_by_circle[circle.id][user.id] for user in users],
            "total": sum(hours_by_circle[circle.id].values(), Decimal()),
        }

        for role in circle.roles.all():
            role_total = sum(hours_by_role[role.id].values(), Decimal())
            if role_total:
                row["roles"].append(
                    {
                        "role": role,
                        "by_user": [hours_by_role[role.id][user.id] for user in users],
                        "total": role_total,
                    }
                )
        if row["total"]:
            circles.append(row)
    return circles
