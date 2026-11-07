"""Objects by their ID or by the code people see in mails and PDFs"""

import re

from django.http import Http404

from workbench.invoices.models import Invoice
from workbench.offers.models import Offer
from workbench.projects.models import Project


PROJECT = r"(?P<year>\d{4})-(?P<project>\d+)"
CODES = {
    Project: re.compile(rf"^{PROJECT}$"),
    Offer: re.compile(rf"^{PROJECT}-o(?P<code>\d+)$"),
    Invoice: re.compile(rf"^{PROJECT}-(?P<code>\d+)$"),
}


def by_id_or_code(queryset, value):
    """The object with this ID (only ASCII digits) or code, e.g. 2026-0042,
    2026-0042-o01 or 2026-0042-0001; invoices without project have five
    digit codes starting with 0 (00042)"""
    model = queryset.model
    value = value.strip().casefold()
    if model is Invoice and len(value) == 5 and value.startswith("0"):
        if obj := queryset.filter(project__isnull=True, _code=int(value)).first():
            return obj
        raise Http404
    if value.isascii() and value.isdigit():
        if obj := queryset.filter(pk=int(value)).first():
            return obj
        raise Http404
    if (pattern := CODES.get(model)) and (match := pattern.match(value)):
        year = int(match["year"])
        # The code contains the year of the project in UTC
        if model is Project:
            candidates = queryset.filter(
                _code=int(match["project"]),
                created_at__year__in=[year - 1, year, year + 1],
            )
        else:
            candidates = queryset.filter(
                _code=int(match["code"]),
                project___code=int(match["project"]),
                project__created_at__year__in=[year - 1, year, year + 1],
            )
        for obj in candidates:
            if obj.code == value:
                return obj
    raise Http404
