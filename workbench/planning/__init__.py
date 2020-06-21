from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.planning.Config"


class Config(AppConfig):
    name = "workbench.planning"
    verbose_name = _("planning")
