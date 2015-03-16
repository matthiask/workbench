from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _


default_app_config = 'stories.Config'


class Config(AppConfig):
    name = 'stories'
    verbose_name = _('stories')
