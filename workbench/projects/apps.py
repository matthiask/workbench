from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class Config(AppConfig):
    name = "workbench.projects"
    verbose_name = _("projects")
