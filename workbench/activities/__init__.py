from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.activities.Config"


class Config(AppConfig):
    name = "workbench.activities"
    verbose_name = _("activities")
