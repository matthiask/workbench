from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.awt.Config"


class Config(AppConfig):
    name = "workbench.awt"
    verbose_name = _("annual working time")
