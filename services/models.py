from datetime import date

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from tools.urls import model_urls


class ServiceType(models.Model):
    title = models.CharField(
        _('title'),
        max_length=40)

    billing_per_hour = models.DecimalField(
        _('billing per hour'),
        max_digits=5,
        decimal_places=2)

    position = models.PositiveIntegerField(
        _('position'),
        default=0)

    class Meta:
        ordering = ('position', 'id')
        verbose_name = _('service type')
        verbose_name_plural = _('service types')

    def __str__(self):
        return self.title


@model_urls()
class RenderedService(models.Model):
    story = models.ForeignKey(
        'stories.Story',
        verbose_name=_('story'),
        related_name='renderedservices',
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
    )
    created_by = models.ForeignKey(
        User,
        verbose_name=_('created by'),
        related_name='+',
    )
    rendered_on = models.DateField(
        _('rendered on'),
        default=date.today,
    )
    rendered_by = models.ForeignKey(
        User,
        verbose_name=_('rendered by'),
        related_name='renderedservices',
    )
    hours = models.DecimalField(
        _('hours'),
        max_digits=5,
        decimal_places=2,
    )
    description = models.TextField(_('description'))

    class Meta:
        ordering = ('-rendered_on', '-created_at')
        verbose_name = _('rendered service')
        verbose_name_plural = _('rendered services')

    def __str__(self):
        return self.description
