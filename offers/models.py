from decimal import Decimal

from django.db import models
from django.db.models import Prefetch
from django.utils.translation import ugettext_lazy as _

from django_pgjson.fields import JsonBField

from accounts.models import User
from projects.models import Project
from stories.models import Story, RequiredService
from tools.models import SearchManager
from tools.urls import model_urls


class OfferManager(SearchManager):
    pass


@model_urls()
class Offer(models.Model):
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
    stories = models.ManyToManyField(
        Story,
        verbose_name=_('stories'),
        blank=True,
        related_name='offers')

    subtotal = models.DecimalField(
        _('subtotal'), max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(
        _('discount'), max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(
        _('tax rate'), max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(
        _('total'), max_digits=10, decimal_places=2, default=0)

    objects = OfferManager()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('offer')
        verbose_name_plural = _('offers')

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self._calculate_total()
        super().save(*args, **kwargs)

    save.alters_data = True

    def _calculate_total(self):
        self.total = self.subtotal - self.discount
        self.total *= 1 + self.tax_rate / 100

    @property
    def tax_amount(self):
        return (self.subtotal - self.discount) * self.tax_rate / 100

    @property
    def code(self):
        return 'O-%06d' % self.pk

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

        self.stories.add(*list(stories))

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
        self.stories.clear()
        self.story_data = {}
        self.subtotal = Decimal('0')
        self._calculate_total()

        if save:
            self.save()
