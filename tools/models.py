from decimal import Decimal

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


def safe_queryset_and(head, *tail):
    """
    Safe AND-ing of querysets. If one of both queries has its
    DISTINCT flag set, sets distinct on both querysets. Also takes extra
    care to preserve the result of the following queryset methods:

    * ``reverse()``
    * ``transform()``
    * ``select_related()``
    * ``prefetch_related()``
    """

    def _merge(qs1, qs2):
        if qs1.query.distinct or qs2.query.distinct:
            res = qs1.distinct() & qs2.distinct()
        else:
            res = qs1 & qs2

        res._transform_fns = list(set(
            getattr(qs1, '_transform_fns', []) +
            getattr(qs2, '_transform_fns', [])))

        if not (qs1.query.standard_ordering and qs2.query.standard_ordering):
            res.query.standard_ordering = False

        select_related = [qs1.query.select_related, qs2.query.select_related]
        if False in select_related:
            # We are not interested in the default value
            select_related.remove(False)

        if len(select_related) == 1:
            res.query.select_related = select_related[0]
        elif len(select_related) == 2:
            if True in select_related:
                # Prefer explicit select_related to generic select_related()
                select_related.remove(True)

            if len(select_related) > 0:
                # If we have two explicit select_related calls, take any
                res.query.select_related = select_related[0]
            else:
                res = res.select_related()

        res._prefetch_related_lookups = list(
            set(qs1._prefetch_related_lookups) |
            set(qs2._prefetch_related_lookups))

        return res

    while tail:
        head = _merge(head, tail[0])
        tail = tail[1:]
    return head


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
            },
        )


class ModelWithTotal(Model):
    subtotal = models.DecimalField(
        _('subtotal'), max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(
        _('discount'), max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(
        _('tax rate'), max_digits=10, decimal_places=2, default=8)
    total = models.DecimalField(
        _('total'), max_digits=10, decimal_places=2, default=0)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self._calculate_total()
        super().save(*args, **kwargs)

    save.alters_data = True

    def _calculate_total(self):
        # Why is the Decimal() coercion necessary??
        self.total = Decimal(self.subtotal) - self.discount
        self.total *= 1 + Decimal(self.tax_rate) / 100
        self.total = self._round_5cents(self.total)

    def _round_5cents(self, value):
        return (value / 5).quantize(Decimal('0.00')) * 5

    @property
    def tax_amount(self):
        return (self.subtotal - self.discount) * self.tax_rate / 100

    @property
    def total_excl_tax(self):
        return self.subtotal - self.discount
