from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = 'services.Config'


class Config(AppConfig):
    name = 'services'
    verbose_name = _('services')
