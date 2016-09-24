from decimal import Decimal
import itertools

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from projects.models import Project
from services.models import ServiceType
from tools.formats import local_date_format
from tools.models import Model, ModelWithTotal, SearchQuerySet, MoneyField
from tools.urls import model_urls


class OfferQuerySet(SearchQuerySet):
    pass


@model_urls()
class Offer(ModelWithTotal):
    IN_PREPARATION = 10
    OFFERED = 20
    ACCEPTED = 30
    REJECTED = 40
    REPLACED = 50

    STATUS_CHOICES = (
        (IN_PREPARATION, _('In preparation')),
        (OFFERED, _('Offered')),
        (ACCEPTED, _('Accepted')),
        (REJECTED, _('Rejected')),
        (REPLACED, _('Replaced')),
    )

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_('project'),
        related_name='offers')

    offered_on = models.DateField(
        _('offered on'),
        blank=True,
        null=True)
    closed_at = models.DateTimeField(
        _('closed at'),
        blank=True,
        null=True)

    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('owned by'),
        related_name='+')

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=IN_PREPARATION)

    postal_address = models.TextField(
        _('postal address'),
        blank=True)

    objects = models.Manager.from_queryset(OfferQuerySet)()

    class Meta:
        ordering = ('-offered_on',)
        verbose_name = _('offer')
        verbose_name_plural = _('offers')

    def __str__(self):
        return self.title

    def _calculate_total(self):
        self.subtotal = sum((item.cost for item in itertools.chain(
            Effort.objects.filter(
                service__offer=self).select_related('service_type'),
            Cost.objects.filter(
                service__offer=self),
        )), Decimal())
        super()._calculate_total()

    def clean(self):
        super().clean()

        if self.status in (self.OFFERED, self.ACCEPTED, self.REJECTED):
            if not self.offered_on:
                raise ValidationError({
                    'status': _(
                        'Offered on date missing for selected state.',
                    ),
                })

    def pretty_status(self):
        if self.status == self.IN_PREPARATION:
            return _('In preparation since %(created_at)s') % {
                'created_at': local_date_format(self.created_at, 'd.m.Y'),
            }
        elif self.status == self.OFFERED:
            return _('Offered on %(offered_on)s') % {
                'offered_on': local_date_format(self.offered_on, 'd.m.Y'),
            }
        elif self.status in (self.ACCEPTED, self.REJECTED):
            return _('%(status)s on %(closed_on)s') % {
                'status': self.get_status_display(),
                'closed_on': local_date_format(self.closed_at, 'd.m.Y'),
            }
        return self.get_status_display()

    def status_css(self):
        return {
            self.IN_PREPARATION: 'success',
            self.OFFERED: 'info',
            self.ACCEPTED: 'default',
            self.REJECTED: 'danger',
            self.REPLACED: '',
        }[self.status]

    @property
    def total_title(self):
        return (
            _('total CHF incl. tax')
            if self.liable_to_vat else _('total CHF'))


@model_urls()
class Service(Model):
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
    )
    offer = models.ForeignKey(
        Offer,
        on_delete=models.CASCADE,
        related_name='services',
        verbose_name=_('offer'),
    )

    title = models.CharField(
        _('title'),
        max_length=200,
    )
    description = models.TextField(
        _('description'),
        blank=True,
    )
    position = models.PositiveIntegerField(
        _('position'),
        default=0,
    )

    effort_hours = models.DecimalField(
        _('effort hours'),
        max_digits=5,
        decimal_places=2,
    )
    _approved_hours = models.DecimalField(
        _('approved hours'),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )
    cost = MoneyField(_('cost'))

    class Meta:
        ordering = ('position', 'created_at')
        verbose_name = _('service')
        verbose_name_plural = _('services')

    def __str__(self):
        return '%s - %s' % (self.offer, self.title)

    def save(self, *args, **kwargs):
        if not self.position:
            max_pos = self.offer.services.aggregate(m=Max('position'))['m']
            self.position = 10 + (max_pos or 0)
        super().save(*args, **kwargs)
        self.offer.save()

    @property
    def approved_hours(self):
        return (
            self.effort_hours if self._approved_hours is None
            else self._approved_hours)

    @classmethod
    def allow_update(cls, instance, request):
        if instance.offer.status > Offer.IN_PREPARATION:
            messages.error(request, _(
                'Cannot modify an offer which is not in preparation anymore.'
            ))
            return False
        return True

    @classmethod
    def allow_delete(cls, instance, request):
        if instance.offer.status > Offer.IN_PREPARATION:
            messages.error(request, _(
                'Cannot modify an offer which is not in preparation anymore.'
            ))
            return False
        return super().allow_delete(instance, request)


class Effort(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='efforts',
        verbose_name=_('service'),
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT,
        verbose_name=_('service type'),
        related_name='+',
    )
    hours = models.DecimalField(
        _('hours'),
        max_digits=5,
        decimal_places=2,
    )

    class Meta:
        ordering = ('service_type',)
        unique_together = (('service', 'service_type'),)
        verbose_name = _('effort')
        verbose_name_plural = _('efforts')

    def __str__(self):
        return '%s' % self.service_type

    @property
    def urls(self):
        return self.service.urls

    def get_absolute_url(self):
        return self.service.get_absolute_url()

    @property
    def cost(self):
        return self.service_type.billing_per_hour * self.hours


class Cost(Model):
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='costs',
        verbose_name=_('service'),
    )
    title = models.CharField(
        _('title'),
        max_length=200,
    )
    cost = MoneyField(_('cost'), default=None)
    position = models.PositiveIntegerField(
        _('position'),
        default=0,
    )

    class Meta:
        ordering = ('position', 'pk')
        verbose_name = _('cost')
        verbose_name_plural = _('costs')

    def __str__(self):
        return self.title

    @property
    def urls(self):
        return self.service.urls

    def get_absolute_url(self):
        return self.service.get_absolute_url()
