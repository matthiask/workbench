from django.apps import AppConfig
from django.utils.translation import pgettext_lazy


class Config(AppConfig):
    name = "workbench.notes"
    verbose_name = pgettext_lazy("notes feature", "notes")
