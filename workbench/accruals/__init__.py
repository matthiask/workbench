from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.accruals.Config"


class Config(AppConfig):
    name = "workbench.accruals"
    verbose_name = _("accruals")
