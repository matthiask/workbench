from django.db import transaction

from workbench.accounts.models import User
from workbench.tools.substitute_with import substitute_with


def merge_services(*, merged, keep):
    """Merge a service into another service of the same project

    The logbook (invoiced entries too), the invoice lines, timestamps and
    pins move, the merged service is deleted. Archived logbook entries
    prevent invoicing the same work twice."""
    assert merged.project_id == keep.project_id
    with transaction.atomic():
        for user in User.objects.filter(pinned_services=merged):
            user.pinned_services.add(keep)
        substitute_with(to_delete=merged, keep=keep)
