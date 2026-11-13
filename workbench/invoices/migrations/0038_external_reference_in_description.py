import datetime as dt

from django.db import migrations
from django.utils import timezone


def copy_external_references(apps, schema_editor):
    """Invoice PDFs showed the current external reference of the project's
    services since 2026-11-10, invoice lines contain it in their description
    now. Copy it into the lines of invoices created since then so that their
    PDFs don't change"""
    Service = apps.get_model("invoices", "Service")
    since = timezone.make_aware(dt.datetime(2026, 11, 10))
    for line in (
        Service.objects
        .filter(invoice__created_at__gte=since)
        .exclude(project_service__external_reference="")
        .select_related("project_service")
    ):
        reference = line.project_service.external_reference.strip()
        if reference and reference not in line.description:
            line.description = "\n".join(
                filter(None, [line.description.rstrip(), reference])
            )
            line.save(update_fields=["description"])


class Migration(migrations.Migration):
    dependencies = [
        ("invoices", "0037_remove_recurringinvoice_flags"),
        ("projects", "0037_external_reference_urls"),
    ]

    operations = [
        migrations.RunPython(copy_external_references, migrations.RunPython.noop),
    ]
