from collections import defaultdict

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _


class WebhookForwardForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        has_webhooks = self.get_webhookconfiguration().exists()

        if has_webhooks:
            self.fields["forward_to_webhook"] = forms.BooleanField(
                label=_("forward change to webhook"),
                initial=False,
                required=False,
            )

    def save(self, *args, **kwargs):
        obj = super().save()

        if self.cleaned_data.get("forward_to_webhook") and (
            webhooks := self.get_webhookconfiguration().all()
        ):
            for webhook in webhooks:
                data = defaultdict()
                for field_name in webhook.forward_fields:
                    if len(field_name_set := field_name.split(".")) == 2:
                        data[field_name_set[1]] = getattr(
                            getattr(obj, field_name_set[0]), field_name_set[1]
                        )

                    else:
                        data[field_name] = getattr(obj, field_name)

                webhook.create_forward(f"{obj.__class__.__name__}-{obj.pk}", dict(data))

        return obj

    def get_webhookconfiguration(self):
        content_type = ContentType.objects.get_for_model(self._meta.model)
        return content_type.webhooks
