from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User


class TimerState(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name=_("user"))
    state = JSONField(_("state"), default=dict)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        verbose_name = _("timer state")
        verbose_name_plural = _("timer states")

    def __str__(self):
        return str(self.user)
