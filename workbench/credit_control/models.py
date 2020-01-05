from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from workbench.credit_control import parsers
from workbench.invoices.models import Invoice
from workbench.tools.models import Model, MoneyField, SearchQuerySet
from workbench.tools.urls import model_urls


# @model_urls
class Ledger(Model):
    PARSER_CHOICES = [
        ("zkb-csv", _("ZKB CSV")),
        ("postfinance-csv", _("PostFinance CSV")),
    ]

    name = models.CharField(_("name"), max_length=100)
    parser = models.CharField(_("parser"), max_length=20, choices=PARSER_CHOICES)

    class Meta:
        ordering = ["name"]
        verbose_name = _("ledger")
        verbose_name_plural = _("ledgers")

    def __str__(self):
        return self.name

    @property
    def parse_fn(self):
        return {
            "zkb-csv": parsers.parse_zkb_csv,
            "postfinance-csv": parsers.parse_postfinance_csv,
        }[self.parser]


class CreditEntryQuerySet(SearchQuerySet):
    def pending(self):
        return self.filter(Q(invoice__isnull=True) & Q(notes=""))

    def processed(self):
        return self.filter(~Q(invoice__isnull=True) | ~Q(notes=""))


@model_urls
class CreditEntry(Model):
    ledger = models.ForeignKey(
        Ledger,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name=_("ledger"),
    )
    reference_number = models.CharField(
        _("reference number"), max_length=40, unique=True
    )
    value_date = models.DateField(_("value date"))
    total = MoneyField(_("total"))
    payment_notice = models.CharField(_("payment notice"), max_length=1000, blank=True)

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("invoice"),
    )
    notes = models.TextField(_("notes"), blank=True)
    _fts = models.TextField(editable=False, blank=True)

    objects = CreditEntryQuerySet.as_manager()

    class Meta:
        ordering = ["-value_date", "-pk"]
        verbose_name = _("credit entry")
        verbose_name_plural = _("credit entries")

    def __str__(self):
        return self.reference_number

    def save(self, *args, **kwargs):
        self._fts = " ".join(str(part) for part in [self.invoice or "", self.total])
        super().save(*args, **kwargs)

    save.alters_data = True
