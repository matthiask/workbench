import re

from django.shortcuts import render
from django.urls import reverse


FALLBACKS = [
    (r"^/projects/(?P<id>[0-9]+)/", lambda kw: ("projects_project", "id", kw["id"])),
    (r"^/offers/(?P<id>[0-9]+)/", lambda kw: ("offers_offer", "id", kw["id"])),
    (r"^/invoices/(?P<id>[0-9]+)/", lambda kw: ("invoices_invoice", "id", kw["id"])),
]


def history_fallback(get_response):
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
