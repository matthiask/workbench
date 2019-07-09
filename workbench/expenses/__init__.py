from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.expenses.Config"


class Config(AppConfig):
    name = "workbench.expenses"
    verbose_name = _("expenses")
