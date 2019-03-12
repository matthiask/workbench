from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.offers.Config"


class Config(AppConfig):
    name = "workbench.offers"
    verbose_name = _("offers")
