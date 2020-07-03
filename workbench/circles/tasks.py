from django.conf import settings
from django.db import transaction
from django.db.models import ProtectedError

import requests

from workbench.circles.models import Circle, Role


def update_circles():
    data = requests.get(
        "https://api.glassfrog.com/api/v3/circles",
        headers={
            "X-Auth-Token": settings.GLASSFROG_TOKEN,
            "Content-Type": "application/json",
        },
    ).json()

    for circle in data["circles"]:
        Circle.objects.update_or_create(
            id=circle["id"], defaults={"name": circle["name"]}
        )

    seen_roles = set()
    for role in data["linked"]["roles"]:
        if not role["links"]["circle"]:
            # Only roles inside circles
            continue
        if role["links"]["supporting_circle"]:
            # No roles of type circle
            pass
            # continue
        if role["is_core"]:
            # Skip core roles
            continue

        # print(role)
        Role.objects.update_or_create(
            id=role["id"],
            defaults={
                "name": role["name_with_circle_for_core_roles"],
                "circle_id": role["links"]["supporting_circle"]
                or role["links"]["circle"],
                "for_circle": bool(role["links"]["supporting_circle"]),
                "is_removed": False,
            },
        )
        seen_roles.add(role["id"])

    for role in Role.objects.exclude(id__in=seen_roles):
        try:
            with transaction.atomic():
                role.delete()
        except ProtectedError:
            role.is_removed = True
            role.save()
