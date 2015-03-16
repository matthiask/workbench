from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = 'offers.Config'


class Config(AppConfig):
    name = 'offers'
    verbose_name = _('offers')
