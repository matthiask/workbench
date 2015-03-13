from decimal import Decimal

from django.db import models
from django.db.models import Prefetch
from django.utils.translation import ugettext_lazy as _

from django_pgjson.fields import JsonBField

from accounts.models import User
from contacts.models import Organization, Person
from projects.models import Project
from stories.models import Story, RequiredService
from tools.models import SearchManager
from tools.urls import model_urls


class InvoiceManager(SearchManager):
    pass


@model_urls()
class Invoice(models.Model):
    IN_PREPARATION = 10
    SENT = 20
    REMINDED = 30
    PAID = 40
    CANCELED = 50
    REPLACED = 60

    STATUS_CHOICES = (
        (IN_PREPARATION, _('In preparation')),
        (SENT, _('Sent')),
        (REMINDED, _('Reminded')),
        (PAID, _('Paid')),
        (CANCELED, _('Canceled')),
        (REPLACED, _('Replaced')),
    )

    FIXED = 'fixed'
    SERVICES = 'services'
    DOWN_PAYMENT = 'down-payment'

    TYPE_CHOICES = (
        (FIXED, _('Fixed')),
        (SERVICES, _('Services')),
        (DOWN_PAYMENT, _('Down payment')),
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
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('project'),
        related_name='+')

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
    type = models.CharField(
        _('type'),
        max_length=20,
        choices=TYPE_CHOICES)
    down_payment_applied_to = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('down payment applied to'),
        related_name='+')

    postal_address = models.TextField(
        _('postal address'),
        blank=True)

    story_data = JsonBField(_('stories'))
    stories = models.ManyToManyField(
        Story,
        verbose_name=_('stories'),
        blank=True,
        related_name='invoices')

    subtotal = models.DecimalField(
        _('subtotal'), max_digits=10, decimal_places=2, default=0)
    discount = models.DecimalField(
        _('discount'), max_digits=10, decimal_places=2, default=0)
    tax_rate = models.DecimalField(
        _('tax rate'), max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(
        _('total'), max_digits=10, decimal_places=2, default=0)

    objects = InvoiceManager()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('invoice')
        verbose_name_plural = _('invoices')

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
        return 'I-%06d' % self.pk

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
