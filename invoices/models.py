from datetime import date
from decimal import Decimal

from django.db import models
from django.db.models import Prefetch
from django.utils.translation import ugettext_lazy as _

from django_pgjson.fields import JsonBField

from accounts.models import User
from contacts.models import Organization, Person
from projects.models import Project
from stories.models import Story, RequiredService
from tools.models import ModelWithTotal, SearchManager
from tools.urls import model_urls


class InvoiceManager(SearchManager):
    pass


@model_urls()
class Invoice(ModelWithTotal):
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
        (FIXED, _('Fixed amount')),
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

    invoiced_on = models.DateField(
        _('invoiced on'),
        blank=True,
        null=True)
    due_on = models.DateField(
        _('due on'),
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

    story_data = JsonBField(_('stories'), blank=True, null=True)
    stories = models.ManyToManyField(
        Story,
        verbose_name=_('stories'),
        blank=True,
        related_name='invoices')

    objects = InvoiceManager()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('invoice')
        verbose_name_plural = _('invoices')

    def __str__(self):
        return self.title

    def pretty_status(self):
        d = {
            'invoiced_on': self.invoiced_on,
            'reminded_on': self.invoiced_on,  # XXX
            'closed_on': self.closed_at.date() if self.closed_at else None,
        }

        if self.status == self.SENT:
            if self.due_on and date.today() > self.due_on:
                return _('Sent on %(invoiced_on)s, but overdue') % d

            return _('Sent on %(invoiced_on)s') % d
        elif self.status == self.REMINDED:
            return _(
                'Sent on %(invoiced_on)s, reminded on %(reminded_on)s'
            ) % d
        elif self.status == self.PAID:
            return _('Paid on %(closed_on)s') % d
        else:
            return self.get_status_display()

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
