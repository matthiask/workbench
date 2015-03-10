from decimal import Decimal

from django.db import models
from django.utils.translation import ugettext_lazy as _

from django_pgjson.fields import JsonBField

from accounts.models import User
from contacts.models import Organization, Person
from services.models import ServiceType
from stories.models import Story
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

    customer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        verbose_name=_('customer'),
        related_name='+')
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('contact'),
        related_name='+')

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

    story_data = JsonBField(_('stories'))
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
        self.total = self.subtotal - self.discount
        self.total *= 1 + self.tax_rate / 100

        super().save(*args, **kwargs)

    save.alters_data = True

    @property
    def tax_amount(self):
        return (self.subtotal - self.discount) * self.tax_rate / 100

    @property
    def code(self):
        return '%06d' % self.pk

    def add_stories(self, stories):
        types = {
            type.id: type.billing_per_hour
            for type in ServiceType.objects.all()}

        if not self.story_data:
            self.story_data = {}

        self.story_data.setdefault('stories', []).extend((
            {
                'title': story.title,
                'description': story.description,
                'billing': [
                    (
                        str(rs.offered_effort),
                        str(types[rs.service_type_id]),
                    ) for rs in story.requiredservices.all()
                ],
            } for story in stories.prefetch_related(
                'requiredservices',
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
