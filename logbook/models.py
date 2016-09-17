from datetime import date

from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from projects.models import Task
from tools.models import SearchManager, Model
from tools.urls import model_urls


@model_urls()
class LoggedHours(Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name='loggedhours',
        verbose_name=_('task'),
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='+',
        verbose_name=_('created by'),
    )
    rendered_on = models.DateField(
        _('rendered on'),
        default=date.today,
    )
    rendered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='loggedhours',
        verbose_name=_('rendered by'),
    )
    hours = models.DecimalField(
        _('hours'),
        max_digits=5,
        decimal_places=2,
    )
    description = models.TextField(
        _('description'),
    )

    invoice = models.ForeignKey(
        'invoices.Invoice',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('invoice'),
        related_name='+',
    )
    archived_at = models.DateTimeField(
        _('archived at'),
        blank=True,
        null=True,
    )

    objects = SearchManager()

    class Meta:
        ordering = ('-rendered_on', '-created_at')
        verbose_name = _('logged hours')
        verbose_name_plural = _('logged hours')

    def __str__(self):
        return self.description
