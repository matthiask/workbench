import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.timezone import is_naive, localtime, make_aware
from django.utils.translation import gettext as _, ngettext


Z0 = Decimal(0)
Z1 = Decimal("0.0")
Z2 = Decimal("0.00")


def round_5cents(value):
    return (value / 5).quantize(Z2, rounding=ROUND_HALF_UP) * 5


def local_date_format(dttm, *, fmt=None):
    if not dttm:
        return ""
    if isinstance(dttm, dt.datetime):
        if is_naive(dttm):
            dttm = make_aware(dttm)
        dttm = localtime(dttm)
    return date_format(
        dttm, fmt or ("d.m.Y H:i" if isinstance(dttm, dt.datetime) else "d.m.Y")
    )


def _fmt(*, fmt, value, exp, plus_sign=False):
    value = value.quantize(exp) if value else exp
    value = value if value != 0 else exp  # Avoid -0.0
    return fmt.format("+" if plus_sign and value > 0 else "", value).replace(",", "’")


def currency(value, plus_sign=False):  # noqa: FBT002
    return _fmt(fmt="{}{:,.2f}", value=value, exp=Z2, plus_sign=plus_sign)


def currency_rounded(value):
    """Whole francs, for reports where cents add nothing"""
    value = Decimal(value or 0).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return f"{value or Decimal(0):,.0f}".replace(",", "’")


def currency_thousands(value):
    """Thousands of francs with one decimal (TCHF), for overviews"""
    value = (Decimal(value or 0) / 1000).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return f"{value or Decimal('0.0'):,.1f}".replace(",", "’")


def total_incl_tax(instance):
    """The total of an offer or invoice; amounts are excl. tax unless
    marked, so it gets a badge if tax applies"""
    value = currency(instance.total)
    if not instance.liable_to_vat:
        return value
    return format_html(
        '{} <span class="badge text-bg-light wb-tax-badge">{}</span>',
        value,
        _("incl. tax"),
    )


def days(value, plus_sign=False):  # noqa: FBT002
    return _fmt(fmt="{}{:,.2f}d", value=value, exp=Z2, plus_sign=plus_sign)


def hours(value, plus_sign=False):  # noqa: FBT002
    return _fmt(fmt="{}{:,.1f}h", value=value, exp=Z1, plus_sign=plus_sign)


def hours_and_minutes(seconds):
    minutes = int(seconds) // 60
    hours, minutes = divmod(minutes, 60)
    parts = [
        (ngettext("%s hour", "%s hours", hours) % hours) if hours else None,
        ngettext("%s minute", "%s minutes", minutes) % minutes,
    ]
    return " ".join(filter(None, parts))
