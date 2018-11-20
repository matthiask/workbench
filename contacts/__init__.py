from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = "contacts.Config"


class Config(AppConfig):
    name = "contacts"
    verbose_name = _("contacts")
