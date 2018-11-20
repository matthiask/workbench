from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = "deals.Config"


class Config(AppConfig):
    name = "deals"
    verbose_name = _("deals")
