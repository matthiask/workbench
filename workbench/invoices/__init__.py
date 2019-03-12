from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.invoices.Config"


class Config(AppConfig):
    name = "workbench.invoices"
    verbose_name = _("invoices")
