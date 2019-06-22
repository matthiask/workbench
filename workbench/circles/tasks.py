import requests

from workbench.circles.models import Circle, Role


def update_circles():
    data = requests.get(
        "https://api.glassfrog.com/api/v3/circles",
        headers={
            "X-Auth-Token": "c0bf9e17fdcdab3467361e3a4f5858d839251d25",
            "Content-Type": "application/json",
        },
    ).json()

    Circle.objects.all().delete()

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
            continue
        if role["is_core"]:
            # Skip core roles
            continue

        print(role)
        Role.objects.update_or_create(
            id=role["id"],
            defaults={
                "name": role["name_with_circle_for_core_roles"],
                "circle_id": role["links"]["circle"],
            },
        )
        seen_roles.add(role["id"])

    Role.objects.exclude(id__in=seen_roles).update(is_removed=True)
