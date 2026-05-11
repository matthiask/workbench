import os.path
import re
from functools import cache

from django import template
from django.conf import settings
from django.utils.html import mark_safe


ASSET_TAGS_RE = re.compile(
    r"<(?:link|script|style)\b[^>]*>(?:.*?</(?:script|style)>)?",
    re.DOTALL | re.IGNORECASE,
)


def rspack_assets(entry):
    base = "tmp" if settings.DEBUG else "static"
    path = os.path.join(settings.BASE_DIR, base, f"{entry}.html")
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return mark_safe(f"<!-- rspack assets missing (entry={entry!r}) -->")
    return mark_safe("".join(ASSET_TAGS_RE.findall(content)))


if not settings.DEBUG:
    rspack_assets = cache(rspack_assets)

register = template.Library()
register.simple_tag(rspack_assets)
