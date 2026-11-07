import re

from django.contrib.messages.storage.base import BaseStorage
from django.http import HttpRequest
from django.shortcuts import render
from django.urls import reverse


FALLBACKS = None


HttpRequest.is_ajax = lambda self: (
    self.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest"
)


def initialize_fallbacks():
    global FALLBACKS  # noqa: PLW0603

    if FALLBACKS:
        return

    from workbench.invoices.models import Invoice, RecurringInvoice
    from workbench.offers.models import Offer
    from workbench.projects.models import Project

    FALLBACKS = [
        (
            r"^{}(?P<id>[0-9]+)/".format(Project.urls["list"]),
            lambda kw: ("projects_project", "id", kw["id"]),
        ),
        (
            r"^{}(?P<id>[0-9]+)/".format(Offer.urls["list"]),
            lambda kw: ("offers_offer", "id", kw["id"]),
        ),
        (
            r"^{}(?P<id>[0-9]+)/".format(Invoice.urls["list"]),
            lambda kw: ("invoices_invoice", "id", kw["id"]),
        ),
        (
            r"^{}(?P<id>[0-9]+)/".format(RecurringInvoice.urls["list"]),
            lambda kw: ("invoices_recurringinvoice", "id", kw["id"]),
        ),
    ]


def history_fallback(get_response):
    initialize_fallbacks()

    def middleware(request):
        response = get_response(request)
        if response.status_code == 404:
            for r, params in FALLBACKS:
                match = re.match(r, request.path_info)
                if match:
                    return render(
                        request,
                        "open-modal.html",
                        {"url": reverse("history", args=params(match.groupdict()))},
                        status=404,
                    )

        return response

    return middleware


class DiscardedMessages(BaseStorage):
    """Messages of forms used by the JSON APIs would show up later in the web
    interface, those requests drop them"""

    def _get(self, *args, **kwargs):
        return [], True

    def _store(self, messages, response, *args, **kwargs):
        return []


def api_messages_middleware(get_response):
    def middleware(request):
        if request.path.startswith("/api/"):
            request._messages = DiscardedMessages(request)
        return get_response(request)

    return middleware
