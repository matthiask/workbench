from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.audit.Config"


class Config(AppConfig):
    name = "workbench.audit"
    verbose_name = _("audit")
