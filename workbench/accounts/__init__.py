from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.accounts.Config"


class Config(AppConfig):
    name = "workbench.accounts"
    verbose_name = _("accounts")
