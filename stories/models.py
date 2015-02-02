from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

from accounts.models import User


class Story(models.Model):
    UNSCHEDULED = 10
    SCHEDULED = 20
    STARTED = 30
    FINISHED = 40
    DELIVERED = 50
    ACCEPTED = 60
    REJECTED = 15

    STATUS_CHOICES = (
        (UNSCHEDULED, _('unscheduled')),
        (SCHEDULED, _('scheduled')),
        (STARTED, _('started')),
        (FINISHED, _('finished')),
        (DELIVERED, _('delivered')),
        (ACCEPTED, _('accepted')),
        (REJECTED, _('rejected')),
    )

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    requested_by = models.ForeignKey(
        User,
        verbose_name=_('requested by'))
    owned_by = models.ManyToManyField(
        User,
        blank=True,
        verbose_name=_('owned by'),
        related_name='owned_stories')
    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)
    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=UNSCHEDULED)
    accepted_at = models.DateTimeField(
        _('accepted at'),
        blank=True,
        null=True)

    effort_best_case = models.DecimalField(
        _('best case effort'),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_('Time required if everything falls into place.'))
    effort_safe_case = models.DecimalField(
        _('safe case effort'),
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
        help_text=_(
            'This story can be delivered in this time frame with'
            ' almost certainty (90%).'))

    due_on = models.DateField(
        _('due on'),
        blank=True,
        null=True,
        help_text=_('This field should be left empty most of the time.'))

    position = models.PositiveIntegerField(_('position'), default=0)

    class Meta:
        ordering = ('position',)
        verbose_name = _('story')
        verbose_name_plural = _('stories')

    def __str__(self):
        return self.title
