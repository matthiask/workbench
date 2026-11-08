"""Merging duplicate people"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from workbench.tools.substitute_with import substitute_with


def merge_errors(*, duplicate, keep):
    """Reasons why the duplicate can't be merged into the person to keep"""
    from workbench.accounts.models import User

    if duplicate.pk == keep.pk:
        return [_("A person cannot be merged with themselves.")]
    if (
        User.objects.filter(person=duplicate).exists()
        and User.objects.filter(person=keep).exists()
    ):
        return [
            _(
                "Both people are linked to a user, unlink one of them in the"
                " user's profile first."
            )
        ]
    return []


def merge_warnings(*, duplicate, keep):
    """``(message, code)`` of things to confirm before merging"""
    from workbench.deals.models import Deal
    from workbench.invoices.models import Invoice, RecurringInvoice
    from workbench.projects.models import Project

    if duplicate.organization_id == keep.organization_id:
        return []
    related = [
        f"{count} {model._meta.verbose_name_plural}"
        for model in [Project, Deal, Invoice, RecurringInvoice]
        if (count := model.objects.filter(contact=duplicate).count())
    ]
    if not related:
        return []
    return [
        (
            _(
                "%(keep)s doesn't belong to the organization of %(duplicate)s."
                " The %(related)s of %(duplicate)s will need a new contact when"
                " changing their customer or contact."
            )
            % {"keep": keep, "duplicate": duplicate, "related": ", ".join(related)},
            "other-organization",
        )
    ]


def _detail_keys(details, fields):
    return {
        tuple(str(getattr(detail, field)).strip().casefold() for field in fields)
        for detail in details
    }


DETAILS = [
    ("emailaddresses", ["email"]),
    ("phonenumbers", ["phone_number"]),
    (
        "postaladdresses",
        [
            "street",
            "house_number",
            "address_suffix",
            "postal_code",
            "city",
            "country",
            "postal_address_override",
        ],
    ),
]


def merge_people(*, duplicate, keep):
    """Move everything of the duplicate to the person to keep and delete it

    Projects, deals, invoices, the linked user and the contact details move
    (details the person to keep has already are dropped), groups are added
    like in the person form, notes are appended and the date of birth is
    taken over if the person to keep has none. The person kept is archived
    only if both were. Name, organization and primary contact stay those of
    the person to keep."""
    if errors := merge_errors(duplicate=duplicate, keep=keep):
        raise ValidationError(errors)

    with transaction.atomic():
        for related_name, fields in DETAILS:
            existing = _detail_keys(getattr(keep, related_name).all(), fields)
            for detail in getattr(duplicate, related_name).all():
                if (key := _detail_keys([detail], fields).pop()) in existing:
                    detail.delete()
                else:
                    existing.add(key)

        for group in duplicate.groups.all():
            keep.add_to_group(group)

        if duplicate.notes.strip() and duplicate.notes.strip() not in keep.notes:
            keep.notes = "\n\n".join(filter(None, (keep.notes, duplicate.notes)))
        keep.date_of_birth = keep.date_of_birth or duplicate.date_of_birth
        # Archived only if both were archived
        keep.is_archived = keep.is_archived and duplicate.is_archived

        substitute_with(to_delete=duplicate, keep=keep)
        # Updates the full text search with the moved details
        keep.save()
        keep.refresh_related_fts()
