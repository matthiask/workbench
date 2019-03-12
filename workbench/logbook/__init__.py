from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.logbook.Config"


class Config(AppConfig):
    name = "workbench.logbook"
    verbose_name = _("logbook")
