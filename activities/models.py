from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from contacts.models import Person
from deals.models import Deal
from projects.models import Project
from tools.urls import model_urls


@model_urls()
class Activity(models.Model):
    contact = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('contact'),
        related_name='activities',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('project'),
        related_name='activities',
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.PROTECT,
        verbose_name=_('deal'),
        blank=True,
        null=True,
        related_name='activities',
    )
    title = models.CharField(_('title'), max_length=200)
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('owned by'),
        related_name='activities',
    )
    due_on = models.DateField(
        _('due on'),
        blank=True,
        null=True,
    )
    time = models.TimeField(
        _('time'),
        blank=True,
        null=True,
    )
    duration = models.DecimalField(
        _('duration'),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_('Duration in hours (if applicable).'),
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
    )
    completed_at = models.DateTimeField(
        _('completed at'),
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _('activity')
        verbose_name_plural = _('activities')

    def __str__(self):
        return self.title
