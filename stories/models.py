from datetime import date

from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _

import reversion

from accounts.models import User
from projects.models import Project, Release
from services.models import ServiceType
from tools.urls import model_urls


@model_urls()
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
        on_delete=models.PROTECT,
        verbose_name=_('requested by'),
        related_name='+')
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('owned by'),
        related_name='+')
    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_('project'),
        related_name='stories')
    release = models.ForeignKey(
        Release,
        on_delete=models.SET_NULL,
        verbose_name=_('release'),
        related_name='stories',
        blank=True,
        null=True)

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=UNSCHEDULED)
    accepted_at = models.DateTimeField(
        _('accepted at'),
        blank=True,
        null=True)

    due_on = models.DateField(
        _('due on'),
        blank=True,
        null=True,
        help_text=_('This field should be left empty most of the time.'))

    position = models.PositiveIntegerField(_('position'), default=0)

    class Meta:
        ordering = ('release', 'position', 'id')
        verbose_name = _('story')
        verbose_name_plural = _('stories')

    def __str__(self):
        return '%s (#%s)' % (self.title, self.pk)

    def overview(self):
        from django.db.models import Sum
        required = self.requiredservices.order_by('service_type').values(
            'service_type__title',
        ).annotate(
            Sum('estimated_effort'),
            Sum('offered_effort'),
            Sum('planning_effort'),
        )

        rendered = self.renderedservices.order_by('rendered_by').values(
            'rendered_by___full_name',
        ).annotate(
            Sum('hours'),
        )

        return list(required), list(rendered)

    def merge_into(self, story):
        with transaction.atomic():
            story_rs = {
                rs.service_type: rs
                for rs in story.requiredservices.all()
            }

            for rs in self.requiredservices.all():
                if rs.service_type in story_rs:
                    obj = story_rs[rs.service_type]
                else:
                    obj = story.requiredservices.model(
                        story=story,
                        service_type=rs.service_type,
                        estimated_effort=0,
                        offered_effort=0,
                        planning_effort=0,
                    )

                obj.estimated_effort += rs.estimated_effort
                obj.offered_effort += rs.offered_effort
                obj.planning_effort += rs.planning_effort
                obj.save()

            self.requiredservices.all().delete()
            self.renderedservices.update(story=story)
            self.delete()


class RequiredService(models.Model):
    story = models.ForeignKey(
        Story,
        on_delete=models.CASCADE,
        verbose_name=_('story'),
        related_name='requiredservices',
    )
    service_type = models.ForeignKey(
        ServiceType,
        on_delete=models.PROTECT,
        verbose_name=_('service type'),
        related_name='+',
    )
    estimated_effort = models.DecimalField(
        _('estimated effort'),
        max_digits=5,
        decimal_places=2,
        help_text=_('The original estimate.'))
    offered_effort = models.DecimalField(
        _('offered effort'),
        max_digits=5,
        decimal_places=2,
        help_text=_('Effort offered to the customer.'))
    planning_effort = models.DecimalField(
        _('planning effort'),
        max_digits=5,
        decimal_places=2,
        help_text=_(
            'Effort for planning. This value should reflect the current '
            ' state of affairs also when work is already in progress.'))

    class Meta:
        ordering = ('service_type',)
        unique_together = (('story', 'service_type'),)
        verbose_name = _('required service')
        verbose_name_plural = _('required services')

    def __str__(self):
        return '%s' % self.service_type

    @property
    def urls(self):
        return self.story.urls

    def get_absolute_url(self):
        return self.story.get_absolute_url()


@model_urls()
class RenderedService(models.Model):
    story = models.ForeignKey(
        Story,
        on_delete=models.PROTECT,
        verbose_name=_('story'),
        related_name='renderedservices',
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now,
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('created by'),
        related_name='+',
    )
    rendered_on = models.DateField(
        _('rendered on'),
        default=date.today,
    )
    rendered_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
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


reversion.register(RequiredService)
# TODO Does it also save the story when required services change?
reversion.register(Story, follow=['requiredservices'])
reversion.register(RenderedService)
