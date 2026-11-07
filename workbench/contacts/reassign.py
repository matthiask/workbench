"""Suggestions for new primary contacts, e.g. when someone left"""

import datetime as dt

from django.utils import timezone


SOURCES = ["project", "deal", "organization_project", "organization_deal"]
# The person's own projects and deals before those of their organization,
# the latest of each tier wins
TIERS = [SOURCES[:2], SOURCES[2:]]


def primary_contact_suggestions(people, *, since=None):
    """``{person_id: suggestion}`` for the people with a suggestion

    The suggestion is the lead of the latest project or the owner of the
    latest deal, whichever is newer, the person's own (as their contact)
    before those of their organization; only active users, only projects and deals created since
    the date if given."""
    from workbench.deals.models import Deal
    from workbench.projects.models import Project

    people = list(people)
    person_ids = {person.pk for person in people}
    organization_ids = {person.organization_id for person in people} - {None}
    cutoff = (
        timezone.make_aware(dt.datetime.combine(since, dt.time.min)) if since else None
    )

    latest = {source: {} for source in SOURCES}
    for model, own, organizations in [
        (Project, "project", "organization_project"),
        (Deal, "deal", "organization_deal"),
    ]:
        queryset = (
            model.objects
            .filter(owned_by__is_active=True)
            .select_related("owned_by")
            .order_by("-created_at", "-pk")
        )
        if cutoff:
            queryset = queryset.filter(created_at__gte=cutoff)
        for item in queryset.filter(contact__in=person_ids):
            latest[own].setdefault(item.contact_id, item)
        for item in queryset.filter(customer__in=organization_ids):
            latest[organizations].setdefault(item.customer_id, item)

    suggestions = {}
    for person in people:
        for tier in TIERS:
            candidates = [
                (item, source)
                for source in tier
                if (
                    item := latest[source].get(
                        person.pk
                        if source in {"project", "deal"}
                        else person.organization_id
                    )
                )
            ]
            if candidates:
                item, source = max(candidates, key=lambda c: c[0].created_at)
                suggestions[person.pk] = {
                    "user": item.owned_by,
                    "source": source,
                    "item": item,
                }
                break
    return suggestions
