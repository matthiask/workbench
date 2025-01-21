from functools import cache

from django import template
from django.conf import settings
from django.utils.html import mark_safe


register = template.Library()


def webpack_assets(entry):
    path = settings.BASE_DIR / ("tmp" if settings.DEBUG else "static") / f"{entry}.html"
    return mark_safe(path.read_text())


if not settings.DEBUG:
    webpack_assets = cache(webpack_assets)
register.simple_tag(webpack_assets)
