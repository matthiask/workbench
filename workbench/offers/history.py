"""Earlier states of a project's offers, rebuilt from the audit log

The audit log has no transaction IDs. Entries of the same user less than
``GAP`` apart form one state, which approximates one save. The states are
rebuilt backwards from the current rows, so pruning old entries doesn't
matter as long as we don't go back further than the audit log is kept
(``prune_audit()``).

Changes which only move services aren't logged (``position`` is excluded
from the audit log of ``projects_service``), the offers save the order in
``Offer.item_order``. Without it (states before the field existed), the
order is the one known at the time; services without known position
(deleted ones) are ordered by the list of service types.
"""

import datetime as dt
from dataclasses import dataclass, field

from django.db import connection
from django.utils import timezone

from workbench.accounts.models import User
from workbench.audit.models import LoggedAction
from workbench.offers.models import Offer, OfferHeading, item_keys, offer_items
from workbench.projects.models import Service
from workbench.services.models import ServiceType
from workbench.tools.history import parse_array


GAP = dt.timedelta(seconds=10)
YEARS = 5

MODELS = {model._meta.db_table: model for model in (Offer, Service, OfferHeading)}


@dataclass
class State:
    """The offers of a project after the changes of one save"""

    event_id: int
    created_at: dt.datetime
    user_name: str
    rows: dict = field(repr=False)
    changed_offer_ids: set = field(default_factory=set)
    _offers: list | None = field(default=None, repr=False)

    def offers(self, project):
        """The offers with their items, oldest first"""
        if self._offers is None:
            self._offers = build_offers(self.rows, project)
        return self._offers


def _current_rows(project):
    """The current rows in the representation of the audit log"""
    rows = {table: {} for table in MODELS}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT hstore(t.*) FROM offers_offer t WHERE project_id = %s",
            [project.pk],
        )
        rows["offers_offer"] = {r[0]["id"]: r[0] for r in cursor.fetchall()}
        cursor.execute(
            "SELECT hstore(t.*) FROM projects_service t WHERE project_id = %s",
            [project.pk],
        )
        rows["projects_service"] = {r[0]["id"]: r[0] for r in cursor.fetchall()}
        cursor.execute(
            "SELECT hstore(t.*) FROM offers_offerheading t WHERE offer_id = ANY(%s)",
            [[int(id) for id in rows["offers_offer"]]],
        )
        rows["offers_offerheading"] = {r[0]["id"]: r[0] for r in cursor.fetchall()}
    return rows


def _actions(project, *, since):
    pk = str(project.pk)
    actions = list(
        LoggedAction.objects.filter(
            table_name__in=["offers_offer", "projects_service"],
            created_at__gte=since,
        ).with_data(project_id=pk)
    )
    offer_ids = {
        a.row_data["id"] for a in actions if a.table_name == "offers_offer"
    } | {
        str(id)
        for id in Offer.objects.filter(project=project).values_list("id", flat=True)
    }
    actions += list(
        LoggedAction.objects.filter(
            table_name="offers_offerheading", created_at__gte=since
        ).filter(row_data__offer_id__in=offer_ids)
    )
    return sorted(actions, key=lambda action: action.event_id)


def _groups(actions):
    """Actions of one user which follow each other closely"""
    groups = []
    for action in actions:
        if (
            groups
            and groups[-1][-1].user_name == action.user_name
            and action.created_at - groups[-1][-1].created_at < GAP
        ):
            groups[-1].append(action)
        else:
            groups.append([action])
    return groups


def _offer_id(action):
    if action.table_name == "offers_offer":
        return action.row_data["id"]
    return action.row_data.get("offer_id") or (action.changed_fields or {}).get(
        "offer_id"
    )


def offer_states(project, *, years=YEARS):
    """The states of the project's offers after each save, newest first"""
    rows = _current_rows(project)
    pk = str(project.pk)
    states = []
    for group in reversed(
        _groups(
            _actions(project, since=timezone.now() - dt.timedelta(days=366 * years))
        )
    ):
        last = group[-1]
        states.append(
            State(
                event_id=last.event_id,
                created_at=last.created_at,
                user_name=last.user_name,
                rows={table: dict(table_rows) for table, table_rows in rows.items()},
                changed_offer_ids={
                    int(id) for action in group if (id := _offer_id(action))
                },
            )
        )
        # Undo the group's changes to get the state before it
        for action in reversed(group):
            table = rows[action.table_name]
            id = action.row_data["id"]
            if action.action == "I":
                table.pop(id, None)
            elif action.action in {"U", "D"}:
                table[id] = action.row_data
            # Services may move between projects
            if (
                action.table_name != "offers_offerheading"
                and table.get(id, {}).get("project_id") != pk
            ):
                table.pop(id, None)
    return states


def _instance(model, row):
    instance = model()
    for f in model._meta.concrete_fields:
        if f.column in row and f.column not in {"fts_document", "item_order"}:
            value = row[f.column]
            setattr(instance, f.attname, None if value is None else f.to_python(value))
    instance._state.adding = False
    return instance


def _ordered_items(services, headings, *, missing, item_order):
    """In the order saved on the offer, else ``offer_items()``, but services
    without known position come last, ordered by the list of service types"""
    keys = {key: index for index, key in enumerate(item_order)}
    items = item_keys([*services, *headings])
    if item_order and all(key in keys for key in items):
        return sorted(
            [*services, *headings],
            key=lambda item: keys[item_keys([item])[0]],
        )
    if not missing:
        return offer_items(services=services, headings=headings)
    type_positions = {
        type.title: index for index, type in enumerate(ServiceType.objects.all())
    }
    known = [service for service in services if service.pk not in missing]
    rest = sorted(
        (service for service in services if service.pk in missing),
        key=lambda service: (
            type_positions.get(service.effort_type, len(type_positions)),
            service.pk,
        ),
    )
    return offer_items(services=known, headings=headings) + rest


def build_offers(rows, project):
    """Unsaved offers with their ``history_items`` (services and headings)"""
    users = User.objects.in_bulk({
        int(row["owned_by_id"]) for row in rows["offers_offer"].values()
    })
    offers = []
    for row in rows["offers_offer"].values():
        offer = _instance(Offer, row)
        offer.project = project
        offer.owned_by = users.get(offer.owned_by_id)
        services, missing = [], set()
        for service_row in rows["projects_service"].values():
            if service_row.get("offer_id") == row["id"]:
                service = _instance(Service, service_row)
                service.project = project
                services.append(service)
                if "position" not in service_row:
                    missing.add(service.pk)
        headings = [
            _instance(OfferHeading, heading_row)
            for heading_row in rows["offers_offerheading"].values()
            if heading_row.get("offer_id") == row["id"]
        ]
        offer.history_items = _ordered_items(
            services,
            headings,
            missing=missing,
            item_order=parse_array(row["item_order"]) if row.get("item_order") else [],
        )
        offers.append(offer)
    return sorted(offers, key=lambda offer: (offer._code, offer.pk))


def state_by_event_id(project, event_id):
    for state in offer_states(project):
        if state.event_id == event_id:
            return state
    return None
