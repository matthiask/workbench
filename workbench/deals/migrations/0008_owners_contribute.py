from django.db import migrations
from django.db.models import Exists, OuterRef


def forwards(apps, schema_editor):
    """Owners contribute to their deals, those who didn't yet are added as a
    contributing force so that most of the credit stays where it was"""
    Deal = apps.get_model("deals", "Deal")
    Contribution = apps.get_model("deals", "Contribution")
    deals = Deal.objects.filter(
        ~Exists(
            Contribution.objects.filter(deal=OuterRef("pk"), user=OuterRef("owned_by"))
        )
    )
    Contribution.objects.bulk_create(
        Contribution(deal_id=deal.pk, user_id=deal.owned_by_id, weight=50)
        for deal in deals
    )


class Migration(migrations.Migration):
    dependencies = [
        ("deals", "0007_attributegroup_show_on_overview"),
    ]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
