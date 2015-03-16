from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = 'accounts.Config'


class Config(AppConfig):
    name = 'accounts'
    verbose_name = _('accounts')
