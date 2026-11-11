"""Merging duplicate people"""

import itertools
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Value
from django.db.models.functions import Concat, Lower, Trim
from django.utils.translation import gettext as _, ngettext

from workbench.contacts.models import ADDRESS_FIELDS, EmailAddress, Person
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


def contact_of(person):
    """``["2 projects", "1 deal"]`` of the objects the person is the contact
    of, which lose their contact when deleting the person"""
    from workbench.deals.models import Deal
    from workbench.invoices.models import Invoice, RecurringInvoice
    from workbench.projects.models import Project

    return [
        f"{count} {ngettext(model._meta.verbose_name, model._meta.verbose_name_plural, count)}"
        for model in [Project, Deal, Invoice, RecurringInvoice]
        if (count := model.objects.filter(contact=person).count())
    ]


def merge_warnings(*, duplicate, keep):
    """``(message, code)`` of things to confirm before merging"""
    if duplicate.organization_id == keep.organization_id:
        return []
    if not (related := contact_of(duplicate)):
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


def _take_primary_contact(*, duplicate, keep):
    """The duplicate's primary contact replaces an inactive one, returns
    whether it did"""
    if not keep.primary_contact.is_active and duplicate.primary_contact.is_active:
        keep.primary_contact = duplicate.primary_contact
        return True
    return False


def merge_organizations(*, duplicate, keep):
    """Move everything of the duplicate organization (people, projects,
    deals, invoices, ...) to the organization to keep and delete it; the
    primary contact stays unless it's an inactive user and the duplicate's
    is active, empty email and billing addresses are taken over"""
    if duplicate.pk == keep.pk:
        raise ValidationError(_("An organization cannot be merged with itself."))
    with transaction.atomic():
        # Groups (e.g. industries) aren't moved by substitute_with()
        keep.groups.add(*duplicate.groups.all())
        changed = _take_primary_contact(duplicate=duplicate, keep=keep)
        for field in ["email", "accounts_payable_email", "default_billing_address"]:
            if not getattr(keep, field) and getattr(duplicate, field):
                setattr(keep, field, getattr(duplicate, field))
                changed = True
        if changed:
            keep.save()
        substitute_with(to_delete=duplicate, keep=keep)
        keep.refresh_related_fts()


def _detail_keys(details, fields):
    return {
        tuple(str(getattr(detail, field)).strip().casefold() for field in fields)
        for detail in details
    }


DETAILS = [
    ("emailaddresses", ["email"]),
    ("phonenumbers", ["phone_number"]),
    ("postaladdresses", ADDRESS_FIELDS),
]


def merge_people(*, duplicate, keep):
    """Move everything of the duplicate to the person to keep and delete it

    Projects, deals, invoices, the linked user and the contact details move
    (details the person to keep has already are dropped), groups are added
    like in the person form, notes are appended and the date of birth is
    taken over if the person to keep has none or one without the year. The person kept is archived
    only if both were. Name and organization stay those of the person to
    keep, the primary contact too unless it's an inactive user and the
    duplicate's is active."""
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
        if duplicate.date_of_birth and (
            not keep.date_of_birth
            or (keep.year_of_birth_unknown and not duplicate.year_of_birth_unknown)
        ):
            keep.date_of_birth = duplicate.date_of_birth
            keep.year_of_birth_unknown = duplicate.year_of_birth_unknown
        # Archived only if both were archived
        keep.is_archived = keep.is_archived and duplicate.is_archived
        _take_primary_contact(duplicate=duplicate, keep=keep)

        substitute_with(to_delete=duplicate, keep=keep)
        # Updates the full text search with the moved details
        keep.save()
        keep.refresh_related_fts()


def _name():
    return Lower(Concat(Trim("given_name"), Value(" "), Trim("family_name")))


def _duplicates_queryset():
    return (
        Person.objects
        .select_related("organization", "primary_contact")
        .prefetch_related("emailaddresses")
        .order_by("is_archived", "pk")
    )


def _name_parts(person):
    return {
        part
        for part in (
            person.given_name.strip().lower(),
            person.family_name.strip().lower(),
        )
        if part
    }


def _may_be_duplicates(a, b):
    """Archived people of other organizations than active people probably
    changed their job, the person form recommends a new person then"""
    return a.is_archived == b.is_archived or a.organization_id == b.organization_id


def duplicates_of(person):
    """People with the same name as the person, or with the same email
    address and a common given or family name (shared addresses like info@
    aren't a reason)"""
    emails = {email.email.strip().lower() for email in person.emailaddresses.all()}
    name = Person.objects.annotate(n=_name()).values("n").get(pk=person.pk)["n"]
    parts = _name_parts(person)
    return [
        other
        for other in _duplicates_queryset()
        .annotate(n=_name())
        .filter(
            Q(n=name)
            | Q(
                pk__in=EmailAddress.objects
                .annotate(e=Lower(Trim("email")))
                .filter(e__in=emails)
                .values("person")
            )
        )
        .exclude(pk=person.pk)
        if (other.n == name or parts & _name_parts(other))
        and _may_be_duplicates(person, other)
    ]


def possible_duplicates():
    """Groups of people with the same name, or with the same email address
    and a common given or family name (also through others: A has B's name
    and C's email address), with at least one person who isn't archived"""
    names = (
        Person.objects
        .annotate(key=_name())
        .values("key")
        .annotate(count=Count("pk"))
        .filter(count__gt=1)
        .values("key")
    )
    emails = (
        EmailAddress.objects
        .annotate(key=Lower(Trim("email")))
        .values("key")
        .annotate(count=Count("person", distinct=True))
        .filter(count__gt=1)
        .values("key")
    )
    by_email = defaultdict(set)
    for pk, key in (
        EmailAddress.objects
        .annotate(key=Lower(Trim("email")))
        .filter(key__in=emails)
        .values_list("person", "key")
    ):
        by_email[key].add(pk)
    parts = {
        person.pk: _name_parts(person)
        for person in Person.objects.filter(
            pk__in=set().union(*by_email.values())
        ).only("given_name", "family_name")
    }

    # Union find of people and the names they share
    parent = {}

    def find(node):
        while parent.setdefault(node, node) != node:
            parent[node] = node = parent[parent[node]]
        return node

    def union(a, b):
        parent[find(a)] = find(b)

    for pk, key in (
        Person.objects
        .annotate(key=_name())
        .filter(key__in=names)
        .values_list("pk", "key")
    ):
        union(("person", pk), ("name", key))
    for pks in by_email.values():
        for a, b in itertools.combinations(sorted(pks), 2):
            if parts[a] & parts[b]:
                union(("person", a), ("person", b))

    groups = defaultdict(list)
    people = _duplicates_queryset().filter(
        pk__in=[pk for kind, pk in parent if kind == "person"]
    )
    for person in people:
        groups[find(("person", person.pk))].append(person)
    for key, group in groups.items():
        organizations = {p.organization_id for p in group if not p.is_archived}
        groups[key] = [
            p for p in group if not p.is_archived or p.organization_id in organizations
        ]
    return sorted(
        (group for group in groups.values() if len(group) > 1),
        key=lambda group: group[0].full_name.casefold(),
    )
