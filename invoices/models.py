from datetime import date

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.html import format_html
from django.utils.formats import date_format
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from contacts.models import Organization, Person
from projects.models import Project
from tools.models import ModelWithTotal, SearchQuerySet
from tools.urls import model_urls


class InvoiceQuerySet(SearchQuerySet):
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
    # TODO do we require a paid_on DateField? Or is the automatically managed
    # closed_at field sufficient?
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

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
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

    objects = models.Manager.from_queryset(InvoiceQuerySet)()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('invoice')
        verbose_name_plural = _('invoices')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._orig_status = self.status

    def __str__(self):
        return '%s %s' % (self.code, self.title)

    def __html__(self):
        return format_html(
            '<small>{}</small> {}',
            self.code,
            self.title,
        )

    def clean(self):
        super().clean()

        if self.status >= self.SENT:
            if not self.invoiced_on or not self.due_on:
                raise ValidationError({
                    'status': _(
                        'Invoice and/or due date missing for selected state.'
                    ),
                })

        if self.invoiced_on and self.due_on:
            if self.invoiced_on > self.due_on:
                raise ValidationError({
                    'due_on': _('Due date has to be after invoice date.'),
                })

    def pretty_status(self):
        d = {
            'invoiced_on': date_format(self.invoiced_on, 'd.m.Y'),
            'reminded_on': date_format(self.invoiced_on,  'd.m.Y'),  # XXX
            'created_at': date_format(self.created_at, 'd.m.Y'),
            'closed_on': (
                date_format(self.closed_at, 'd.m.Y')
                if self.closed_at else None),
        }

        if self.status == self.IN_PREPARATION:
            return _('In preparation since %(created_at)s') % d
        elif self.status == self.SENT:
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
