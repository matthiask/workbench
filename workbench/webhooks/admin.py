from workbench.tools import admin
from workbench.webhooks import models


@admin.register(models.WebhookConfiguration)
class WebhookConfigurationAdmin(admin.ReadWriteModelAdmin):
    pass


@admin.register(models.WebhookForward)
class WebhookForwardAdmin(admin.ModelAdmin):
    pass
