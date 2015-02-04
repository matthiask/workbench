from django.core.urlresolvers import reverse
from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from services.models import ServiceType
from tools.urls import model_urls


@model_urls()
class Funnel(models.Model):
    title = models.CharField(
        _('funnel'),
        max_length=200)

    class Meta:
        ordering = ('title',)
        verbose_name = _('funnel')
        verbose_name_plural = _('funnels')

    def __str__(self):
        return self.title


@model_urls()
class Deal(models.Model):
    INITIAL = 10
    NEGOTIATING = 20
    IMPROBABLE = 30
    PROBABLE_FUTURE = 40
    PROBABLE_SOON = 50
    ACCEPTED = 60
    DECLINED = 70

    STATUS_CHOICES = (
        (INITIAL, _('initial')),
        (NEGOTIATING, _('negotiating')),
        (IMPROBABLE, _('improbable')),
        (PROBABLE_FUTURE, _('probable in the future')),
        (PROBABLE_FUTURE, _('probable soon')),
        (ACCEPTED, _('accepted')),
        (DECLINED, _('declined')),
    )

    funnel = models.ForeignKey(
        Funnel,
        verbose_name=_('funnel'),
        related_name='deals')

    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)
    owned_by = models.ForeignKey(
        User,
        verbose_name=_('owned by'))
    estimated_value = models.DecimalField(
        _('estimated value'),
        max_digits=10,
        decimal_places=2)

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=INITIAL)

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    closed_at = models.DateTimeField(
        _('closed at'),
        blank=True,
        null=True)

    class Meta:
        verbose_name = _('deal')
        verbose_name_plural = _('deals')

    def __str__(self):
        return self.title


class RequiredService(models.Model):
    deal = models.ForeignKey(
        Deal,
        verbose_name=_('deal'),
        related_name='required_services')
    service_type = models.ForeignKey(
        ServiceType,
        verbose_name=_('service type'),
        related_name='+')
    hours = models.DecimalField(
        _('hours'),
        max_digits=5,
        decimal_places=2)

    class Meta:
        verbose_name = _('required service')
        verbose_name_plural = _('required services')

    def __str__(self):
        return '%.2fh %s' % (self.hours, self.service_type)
