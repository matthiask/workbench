from django.db import migrations


# The previous colors and calmer ones of the same hue for the planning
# grid. Only exact matches are changed, colors chosen otherwise are kept.
COLORS = {
    "#471199": "#6741d9",
    "#7b2199": "#9c36b5",
    "#315a99": "#3b5bdb",
    "#203a63": "#5c7cfa",
    "#338899": "#1098ad",
    "#42d4ff": "#22b8cf",
    "#6ec4d2": "#66d9e8",
    "#08993d": "#2f9e44",
    "#29c286": "#20c997",
    "#ffd254": "#fcc419",
    "#d9a925": "#f08c00",
    "#27cd71": "#69db7c",
    "#999999": "#868e96",
    "#8c8c8c": "#adb5bd",
    "#ffccf6": "#f783ac",
}


def _recolor(apps, mapping):
    ServiceType = apps.get_model("services", "ServiceType")
    for service_type in ServiceType.objects.all():
        if new := mapping.get(service_type.color.lower()):
            service_type.color = new
            service_type.save(update_fields=["color"])


def forwards(apps, schema_editor):
    _recolor(apps, COLORS)


def backwards(apps, schema_editor):
    # Research and groundwork shared a color before, both get it back
    _recolor(apps, {new: old for old, new in COLORS.items()})


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0005_servicetype_color"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
