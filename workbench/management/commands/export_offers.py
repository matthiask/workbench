import json

from django.core.management.base import BaseCommand
from django.core.serializers.json import DjangoJSONEncoder

from workbench.offers.models import Offer


class Command(BaseCommand):
    help = "Export accepted offers and their services as JSON"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            help="Output file path (defaults to stdout)",
        )

    def handle(self, **options):
        # Get accepted offers with their services
        offers = (
            Offer.objects
            .accepted()
            .select_related("project", "owned_by")
            .prefetch_related("services")
        )

        data = []

        for offer in offers:
            offer_data = {
                "id": offer.id,
                "code": offer.code,
                "title": offer.title,
                "description": offer.description,
                "status": offer.get_status_display(),
                "offered_on": offer.offered_on,
                "closed_on": offer.closed_on,
                "project": {
                    "id": offer.project.id,
                    "code": offer.project.code,
                    "title": offer.project.title,
                    "customer": offer.project.customer.name,
                },
                "owned_by": {
                    "id": offer.owned_by.id,
                    "name": offer.owned_by.get_full_name(),
                },
                "services": [],
            }

            for service in offer.services.all():
                service_data = {
                    "id": service.id,
                    "title": service.title,
                    "description": service.description,
                    "effort_hours": float(service.effort_hours or 0),
                    "effort_rate": float(service.effort_rate or 0),
                    "cost": float(service.cost or 0),
                    "third_party_costs": float(service.third_party_costs or 0),
                    "allow_logging": service.allow_logging,
                    "is_optional": service.is_optional,
                }
                offer_data["services"].append(service_data)

            data.append(offer_data)

        json_output = json.dumps(data, indent=2, cls=DjangoJSONEncoder)

        if options["output"]:
            with open(options["output"], "w", encoding="utf-8") as f:
                f.write(json_output)
            self.stdout.write(f"Exported {len(data)} offers to {options['output']}")
        else:
            self.stdout.write(json_output)
