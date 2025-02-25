from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _


class WebhookForward(models.Model):
    content_object = models.CharField(_("content object"), max_length=200)
    forwarded_at = models.DateTimeField(_("forwarded at"), blank=True, null=True)
    forward_data = models.JSONField(_("forward data"))
    forwarding_last_failed_at = models.DateTimeField(
        _("forwarding last failed at"), blank=True, null=True
    )
    forwarding_retry_count = models.PositiveIntegerField(
        _("forwarding retry count"), default=0
    )
    forwarding_error_log = models.TextField(_("forwarding error log"), blank=True)
    configuration = models.ForeignKey(
        "webhooks.WebhookConfiguration", on_delete=models.PROTECT
    )

    def __str__(self):
        return f"{self.content_object!s}"


class WebhookConfiguration(models.Model):
    title = models.CharField(_("title"), max_length=50)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, related_name="webhooks"
    )
    webhook_url = models.URLField(_("webhook url"))
    forward_fields = models.JSONField(
        _("forward fields"),
        blank=True,
        help_text=_(
            'JSON representation of fields to be submitted. E.g. \'["email", "person.given_name", "person.family_name"]\''
        ),
    )

    def __str__(self):
        return str(self.title)

    def create_forward(self, content_object, data):
        WebhookForward.objects.create(
            content_object=content_object, forward_data=data, configuration=self
        )
