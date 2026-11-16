from django.db import migrations


def backfill(apps, schema_editor):
    """The order of services and headings of existing offers, like
    ``offer_items()``; one audit log entry per offer, which the offer
    history skips"""
    Offer = apps.get_model("offers", "Offer")
    OfferHeading = apps.get_model("offers", "OfferHeading")
    Service = apps.get_model("projects", "Service")

    items = {}
    for service in Service.objects.filter(offer__isnull=False).values_list(
        "offer_id", "position", "pk"
    ):
        items.setdefault(service[0], []).append((service[1], 1, service[2], "s"))
    for heading in OfferHeading.objects.values_list("offer_id", "position", "pk"):
        items.setdefault(heading[0], []).append((heading[1], 0, heading[2], "h"))
    for offer_id, offer_items in items.items():
        Offer.objects.filter(pk=offer_id, item_order=[]).update(
            item_order=[f"{kind}{pk}" for *_rest, pk, kind in sorted(offer_items)]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("offers", "0019_offer_item_order"),
        ("projects", "0037_external_reference_urls"),
    ]

    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
