import re

from django.shortcuts import render
from django.urls import reverse


FALLBACKS = None


def initialize_fallbacks():
    global FALLBACKS

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
