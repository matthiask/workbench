from decimal import Decimal
from functools import partial
from itertools import islice

from django.contrib import messages
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import ProtectedError
from django.db.models.deletion import Collector
from django.utils.translation import gettext, gettext_lazy as _

from workbench.tools.formats import Z2, currency
from workbench.tools.search import search


class SearchQuerySet(models.QuerySet):
    def search(self, terms):
        return search(self, terms)


class SlowCollector(Collector):
    def can_fast_delete(self, *args, **kwargs):
        return False


class Model(models.Model):
    objects = SearchQuerySet.as_manager()

    class Meta:
        abstract = True

    @classmethod
    def allow_create(cls, request):
        return True

    @classmethod
    def allow_update(cls, instance, request):
        return True

    @classmethod
    def allow_delete(cls, instance, request):
        collector = SlowCollector(using=instance._state.db)
        try:
            collector.collect([instance])
        except ProtectedError as exc:
            messages.error(
                request,
                gettext(
                    "Cannot delete '%(object)s'"
                    " because of related objects (%(related)s)."
                )
                % {
                    "object": instance,
                    "related": ", ".join(
                        str(o) for o in islice(exc.protected_objects, 10)
                    ),
                },
            )
            return False
        else:
            return True

    @classmethod
    def get_redirect_url(cls, instance, request):
        return None

    @property
    def code(self):
        return "%05d" % self.pk if self.pk else ""

    @property
    def pretty_status(self):
        return self.get_status_display() if hasattr(self, "get_status_display") else ""


ONE = Decimal("1")


MoneyField = partial(
    models.DecimalField,
    max_digits=10,
    decimal_places=2,
    validators=[MinValueValidator(0)],
)


HoursField = partial(
    models.DecimalField,
    max_digits=10,
    decimal_places=1,
    validators=[MinValueValidator(0)],
)


HoursFieldAllowNegatives = partial(models.DecimalField, max_digits=10, decimal_places=1)


class ModelWithTotal(Model):
    subtotal = MoneyField(_("subtotal"), default=Z2)
    discount = MoneyField(_("discount"), default=Z2)
    liable_to_vat = models.BooleanField(
        _("liable to VAT"),
        default=True,
        help_text=_(
            "For example invoices to foreign institutions are not liable to VAT."
        ),
    )
    total_excl_tax = MoneyField(_("total excl. tax"), default=Z2)
    tax_rate = MoneyField(_("tax rate"), default=Decimal("7.7"))
    total = MoneyField(_("total"), default=Z2)
    show_service_details = models.BooleanField(_("show service details"), default=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self._calculate_total()
        super().save(*args, **kwargs)

    save.alters_data = True

    def _calculate_total(self):
        self.total_excl_tax = (
            self.subtotal - self.discount - getattr(self, "down_payment_total", Z2)
        )
        self.total = self._round_5cents(
            (self.total_excl_tax * (1 + self.tax_rate / 100))
            if self.liable_to_vat
            else self.total_excl_tax
        )

    def _round_5cents(self, value):
        return (value / 5).quantize(Decimal("0.00")) * 5

    @property
    def tax_amount(self):
        return self.total_excl_tax * self.tax_rate / 100 if self.liable_to_vat else Z2

    @property
    def pretty_total_excl(self):
        parts = [gettext("%s excl. tax") % currency(self.total_excl_tax)]
        if self.discount:
            parts.append(" (%s %s)" % (currency(self.discount), gettext("discount")))
        return "".join(parts)
