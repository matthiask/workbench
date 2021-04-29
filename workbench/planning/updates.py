import datetime as dt

from django.utils import timezone

from workbench.audit.models import LoggedAction, audit_user_id
from workbench.planning.models import Milestone, PlannedWork


def updated():
    queryset = LoggedAction.objects.filter(
        created_at__gte=timezone.now() - dt.timedelta(hours=48)
    )

    return {
        "planned_work": [
            row
            for row in [
                {
                    "by": audit_user_id(row["user_name"]),
                    "id": int(row["row_data__id"]),
                    "user_id": int(row["row_data__user_id"]),
                    "action": row["action"],
                }
                for row in queryset.for_model(PlannedWork).values(
                    "user_name", "action", "row_data__id", "row_data__user_id"
                )
            ]
            if row["by"] != row["user_id"]
        ],
        "milestones": [
            {
                "by": audit_user_id(row["user_name"]),
                "id": int(row["row_data__id"]),
                "action": row["action"],
            }
            for row in queryset.for_model(Milestone).values(
                "user_name", "action", "row_data__id"
            )
        ],
    }


def test():  # pragma: no cover
    from pprint import pprint

    pprint(updated())
