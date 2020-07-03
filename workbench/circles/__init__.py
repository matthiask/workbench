from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


default_app_config = "workbench.circles.Config"


class Config(AppConfig):
    name = "workbench.circles"
    verbose_name = _("circles")
