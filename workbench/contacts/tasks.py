import datetime as dt
import operator
from functools import reduce

from django.conf import settings
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from requests import HTTPError, api

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction
from workbench.contacts.models import (
    EmailAddress,
    Group,
    Organization,
    Person,
    PhoneNumber,
    PostalAddress,
)
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.planning.models import ExternalWork
from workbench.projects.models import Campaign, Project


def upload_contacts_to_brevo():
    # Determine persons that need to be updated. Get machting emails
    # and addresses
    since = timezone.now().replace(hour=0, minute=0, second=0)
    since -= dt.timedelta(days=1)

    person_ids = {
        int(row.row_data["id"])
        for row in LoggedAction.objects.filter(
            created_at__gte=since, table_name=Person._meta.db_table, action="I"
        )
    }

    person_ids |= {
        int(row.row_data["person_id"])
        for row in LoggedAction.objects.filter(
            created_at__gte=since, table_name=EmailAddress._meta.db_table, action="I"
        )
    }

    persons_to_sync = Person.objects.active().filter(id__in=person_ids)

    emails = {
        obj.person_id: obj
        for obj in EmailAddress.objects.filter(person__in=persons_to_sync).order_by(
            "-weight", "-id"
        )
    }

    # Update person by person
    for person in persons_to_sync:
        email = emails.get(person.id)

        # Skip all persons that don't have an email
        if not email:
            continue

        logged_action = LoggedAction.objects.get(
            table_name=Person._meta.db_table, row_data__id=person.id, action="I"
        )

        if not logged_action:
            continue

        forward_data = {
            "email": email.email,
            "given_name": person.given_name,
            "family_name": person.family_name,
            "salutation": person.address,
            "full_salutation": person.salutation,
            "primary_contact": person.primary_contact.get_full_name(),
            "created_at": str(logged_action.created_at),
            "groups": ", ".join([g.title for g in person.groups.all()]),
            "organization": person.organization.name if person.organization else "",
        }

        # send to brevo
        try:
            api.post(settings.BREVO_WEBHOOK_URL, json=forward_data)
        except HTTPError as err:
            print(err)


def _changed_since(cutoff, model, *, key="id"):
    """IDs of the instances changed since the cutoff according to the audit
    log (which keeps contact changes for five years)"""
    return {
        int(row_data[key])
        for row_data in LoggedAction.objects.filter(
            table_name=model._meta.db_table, created_at__gte=cutoff
        ).values_list("row_data", flat=True)
        if row_data.get(key)
    }


# Contact details do not keep people active, their changes do (see below)
NEVER = Q(pk__in=[])


def _recent(cutoff):
    """Which related objects keep contacts active. Contacts referenced by
    models not listed here are always kept."""
    projects = (
        Q(closed_on__isnull=True) | Q(closed_on__gte=cutoff) | Q(created_at__gte=cutoff)
    )
    return {
        Project: projects,
        Campaign: Q(
            Exists(
                Project.objects.filter(projects, campaign=OuterRef("pk")),
            )
        ),
        Deal: Q(closed_on__isnull=True) | Q(created_at__gte=cutoff),
        Invoice: Q(created_at__gte=cutoff),
        RecurringInvoice: Q(ends_on__isnull=True) | Q(ends_on__gte=cutoff),
        ExternalWork: Q(created_at__gte=cutoff),
        User: Q(is_active=True),
        Person: Q(is_archived=False),
        PhoneNumber: NEVER,
        EmailAddress: NEVER,
        PostalAddress: NEVER,
    }


def _reverse_relations(model):
    return [
        field
        for field in model._meta.get_fields()
        if field.auto_created and field.is_relation and not field.concrete
    ]


def _unused(model, cutoff, *, changed):
    """Active instances which aren't referenced by anything recent, aren't
    in active groups and weren't changed since the cutoff"""
    recent = _recent(cutoff)
    keep = [
        Exists(
            field.related_model._base_manager.filter(
                recent.get(field.related_model, Q()),
                **{field.field.name: OuterRef("pk")},
            )
        )
        for field in _reverse_relations(model)
        if recent.get(field.related_model) is not NEVER
    ]
    keep.append(
        Exists(
            Group.objects.filter(
                is_archived=False, **{model._meta.model_name: OuterRef("pk")}
            )
        )
    )
    return (
        model.objects
        .filter(is_archived=False)
        .exclude(id__in=changed)
        .exclude(reduce(operator.or_, keep))
    )


def unused_people(cutoff):
    changed = _changed_since(cutoff, Person)
    for detail in [PhoneNumber, EmailAddress, PostalAddress]:
        changed |= _changed_since(cutoff, detail, key="person_id")
    return _unused(Person, cutoff, changed=changed)


def unused_organizations(cutoff):
    """Organizations with active people are kept"""
    return _unused(Organization, cutoff, changed=_changed_since(cutoff, Organization))


def archive_unused_contacts():
    """Contacts nobody used for five years are archived (data minimization),
    people first because organizations with active people are kept"""
    cutoff = timezone.now() - dt.timedelta(days=5 * 365)
    Person.objects.filter(id__in=unused_people(cutoff)).update(is_archived=True)
    Organization.objects.filter(id__in=unused_organizations(cutoff)).update(
        is_archived=True
    )
