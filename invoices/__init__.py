from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = "invoices.Config"


class Config(AppConfig):
    name = "invoices"
    verbose_name = _("invoices")
