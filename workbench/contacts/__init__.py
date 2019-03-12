from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.contacts.Config"


class Config(AppConfig):
    name = "workbench.contacts"
    verbose_name = _("contacts")
