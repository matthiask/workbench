from decimal import Decimal

from django.db import models
from django.db.models import Prefetch
from django.utils.translation import ugettext_lazy as _

from django_pgjson.fields import JsonBField

from accounts.models import User
from projects.models import Project
from stories.models import RequiredService
from tools.models import ModelWithTotal, SearchManager
from tools.urls import model_urls


class OfferManager(SearchManager):
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

    story_data = JsonBField(_('stories'), blank=True, null=True)

    objects = OfferManager()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('offer')
        verbose_name_plural = _('offers')

    def __str__(self):
        return self.title

    def add_stories(self, stories, save=True):
        if not self.story_data:
            self.story_data = {}

        self.story_data.setdefault('stories', []).extend((
            {
                'title': story.title,
                'description': story.description,
                'billing': [
                    (
                        str(rs.offered_effort),
                        str(rs.service_type.billing_per_hour),
                    ) for rs in story.requiredservices.all()
                ],
            } for story in stories.prefetch_related(
                Prefetch(
                    'requiredservices',
                    queryset=RequiredService.objects.select_related(
                        'service_type'),
                ),
            )
        ))

        stories.update(offer=self)

        self.subtotal = sum([
            sum(
                (Decimal(e) * Decimal(p) for e, p in story['billing']),
                Decimal('0')
            )
            for story in self.story_data['stories']
        ], Decimal('0'))

        self._calculate_total()

        if save:
            self.save()

    def clear_stories(self, save=True):
        self.stories.update(offer=None)
        self.story_data = {}
        self.subtotal = Decimal('0')
        self._calculate_total()

        if save:
            self.save()
