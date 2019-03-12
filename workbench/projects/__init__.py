from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.projects.Config"


class Config(AppConfig):
    name = "workbench.projects"
    verbose_name = _("projects")
