from collections import defaultdict

from django.db.models import Sum

from workbench.accounts.models import User
from workbench.contacts.models import Organization
from workbench.logbook.models import LoggedHours
from workbench.tools.formats import Z1


def hours_per_customer(date_range, *, users=None):
    hours = defaultdict(lambda: defaultdict(lambda: Z1))
    user_hours = defaultdict(lambda: Z1)
    seen_organizations = set()
    seen_users = set()

    queryset = LoggedHours.objects.order_by().filter(rendered_on__range=date_range)
    if users:
        queryset = queryset.filter(rendered_by__in=users)

    for row in queryset.values("rendered_by", "service__project__customer").annotate(
        Sum("hours")
    ):
        hours[row["service__project__customer"]][row["rendered_by"]] = row["hours__sum"]
        user_hours[row["rendered_by"]] += row["hours__sum"]
        seen_organizations.add(row["service__project__customer"])
        seen_users.add(row["rendered_by"])

    organizations = []
    user_list = User.objects.filter(id__in=seen_users)

    for org in Organization.objects.filter(id__in=seen_organizations):
        organizations.append(
            {
                "organization": org,
                "user_hours": [(user, hours[org.id][user.id]) for user in user_list],
                "total_hours": sum(hours[org.id].values(), Z1),
            }
        )

    return {
        "organizations": sorted(
            organizations, key=lambda row: row["total_hours"], reverse=True
        ),
        "users": user_list,
        "user_hours": [(user, user_hours[user.id]) for user in user_list],
        "total_hours": sum(user_hours.values(), Z1),
    }
