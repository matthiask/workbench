from datetime import date

from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from offers.models import Service
from projects.models import Project, Task
from tools.models import SearchManager, Model, MoneyField, HoursField
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
    hours = HoursField(
        _('hours'),
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
        return '%s: %s' % (self.task.title, self.description)

    def __html__(self):
        return format_html(
            '{}:<br>{}',
            self.task.title,
            self.description)


@model_urls(default='update')
class LoggedCost(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name='loggedcosts',
        verbose_name=_('project'),
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.PROTECT,
        related_name='loggedcosts',
        verbose_name=_('service'),
        blank=True,
        null=True,
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
    cost = MoneyField(
        _('cost'),
        default=None,
        help_text=_('Total incl. tax for third-party costs.'),
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
        verbose_name = _('logged cost')
        verbose_name_plural = _('logged cost')

    def __str__(self):
        return self.description
