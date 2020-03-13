from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.notes.Config"


class Config(AppConfig):
    name = "workbench.notes"
    verbose_name = _("notes")
