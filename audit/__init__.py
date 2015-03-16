from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = 'audit.Config'


class Config(AppConfig):
    name = 'audit'
    verbose_name = _('audit')
