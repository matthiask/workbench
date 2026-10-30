"""The search across projects, contacts, invoices, offers and deals"""

from urllib.parse import urlencode

from django.urls import reverse
from django.utils.text import capfirst
from ninja import Field, Query, Router, Schema

from workbench.accounts.features import FEATURES
from workbench.contacts.models import Organization, Person
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.offers.models import Offer
from workbench.projects.models import Campaign, Project


# The nouns of the wb command line interface
NOUNS = {
    Project: "projects",
    Campaign: "campaigns",
    Organization: "organizations",
    Person: "people",
    Invoice: "invoices",
    RecurringInvoice: "recurring-invoices",
    Offer: "offers",
    Deal: "deals",
}


def search_sources(user):
    """The querysets the user may search"""
    sources = [Project.objects.select_related("owned_by")]
    if user.features[FEATURES.CAMPAIGNS]:
        sources.append(Campaign.objects.select_related("owned_by"))
    sources.extend([
        Organization.objects.active(),
        Person.objects.active().select_related("organization"),
    ])
    if user.features[FEATURES.CONTROLLING]:
        sources.extend([
            Invoice.objects.select_related("project", "owned_by"),
            RecurringInvoice.objects.all(),
            Offer.objects.select_related("project", "owned_by").order_by("-pk"),
            Deal.objects.order_by("-pk"),
        ])
    return sources


def list_url(model):
    return reverse(f"{model._meta.app_label}_{model._meta.model_name}_list")


router = Router(tags=["search"])


class SearchFilter(Schema):
    q: str = Field(min_length=1)
    limit: int = Field(10, ge=1, le=100)


class SearchResult(Schema):
    id: int
    url: str
    title: str


class SearchGroup(Schema):
    type: str
    label: str
    url: str
    count: int
    items: list[SearchResult]


@router.get("/search/", response=list[SearchGroup])
def search(request, filters: Query[SearchFilter]):
    """Search everything like the search field of the web interface, at most
    ``limit`` results per type; ``type`` is the noun of the CLI"""
    groups = []
    for queryset in search_sources(request.user):
        results = queryset.search(filters.q)
        model = queryset.model
        groups.append({
            "type": NOUNS[model],
            "label": str(capfirst(model._meta.verbose_name_plural)),
            "url": request.build_absolute_uri(
                f"{list_url(model)}?{urlencode({'q': filters.q})}"
            ),
            "count": results.count(),
            "items": [
                {
                    "id": obj.pk,
                    "url": request.build_absolute_uri(obj.get_absolute_url()),
                    "title": str(obj),
                }
                for obj in results[: filters.limit]
            ],
        })
    return groups
