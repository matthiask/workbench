from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.deals.Config"


class Config(AppConfig):
    name = "workbench.deals"
    verbose_name = _("deals")
