from django.db import models
from django.utils.translation import ugettext_lazy as _


class ServiceType(models.Model):
    title = models.CharField(
        _('title'),
        max_length=40)

    billing_per_hour = models.DecimalField(
        _('billing per hour'),
        max_digits=5,
        decimal_places=2)

    position = models.PositiveIntegerField(
        _('position'),
        default=0)

    class Meta:
        ordering = ('position', 'id')
        verbose_name = _('service type')
        verbose_name_plural = _('service types')

    def __str__(self):
        return self.title
