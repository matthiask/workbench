from decimal import Decimal
from functools import partial

from django.contrib import messages
from django.db import models
from django.db.models import ProtectedError
from django.db.models.deletion import Collector
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _, ugettext

from tools.search import search


class SearchQuerySet(models.QuerySet):
    def search(self, terms):
        return search(self, terms)


SearchManager = models.Manager.from_queryset(SearchQuerySet)


class Model(models.Model):
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
        collector = Collector(using=instance._state.db)
        try:
            collector.collect([instance])
        except ProtectedError as exc:
            messages.error(
                request,
                ugettext(
                    "Cannot delete '%(object)s'"
                    " because of related objects (%(related)s)."
                ) % {
                    'object': instance,
                    'related': ', '.join(
                        str(o) for o in exc.protected_objects[:10]),
                })
            return False
        else:
            return True

    def css(self):
        return ''

    @property
    def code(self):
        return '%05d' % self.pk

    def pretty_status(self):
        return self.get_status_display()

    def snippet(self):
        opts = self._meta
        return render_to_string(
            [
                '%s/%s_snippet.html' % (
                    opts.app_label,
                    opts.model_name.lower()),
                'tools/object_snippet.html',
            ],
            {
                'object': self,
                opts.model_name.lower(): self,
                'verbose_name': opts.verbose_name,
            },
        )


MoneyField = partial(
    models.DecimalField,
    max_digits=10,
    decimal_places=2,
    default=Decimal('0'),
)


HoursField = partial(
    models.DecimalField,
    max_digits=5,
    decimal_places=2,
)


class ModelWithTotal(Model):
    subtotal = MoneyField(_('subtotal'))
    discount = MoneyField(_('discount'))
    liable_to_vat = models.BooleanField(
        _('liable to VAT'), default=True,
        help_text=_(
            'For example invoices to foreign institutions are not'
            ' liable to VAT.'
        ))
    tax_rate = MoneyField(_('tax rate'), default=Decimal('8'))
    total = MoneyField(_('total'))

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self._calculate_total()
        super().save(*args, **kwargs)

    save.alters_data = True

    def _calculate_total(self):
        self.total = self.total_excl_tax
        if self.liable_to_vat:
            self.total *= 1 + self.tax_rate / 100
        self.total = self._round_5cents(self.total)

    def _round_5cents(self, value):
        return (value / 5).quantize(Decimal('0.00')) * 5

    @property
    def tax_amount(self):
        return (
            self.total_excl_tax * self.tax_rate / 100
            if self.liable_to_vat else Decimal())

    @property
    def total_excl_tax(self):
        return self.subtotal - self.discount
