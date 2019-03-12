from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.services.Config"


class Config(AppConfig):
    name = "workbench.services"
    verbose_name = _("services")
