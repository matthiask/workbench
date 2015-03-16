from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = 'activities.Config'


class Config(AppConfig):
    name = 'activities'
    verbose_name = _('activities')
