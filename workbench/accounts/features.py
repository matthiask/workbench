from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext as _


def feature_required(feature):
    def decorator(view):
        @wraps(view)
        def require_feature(request, *args, **kwargs):
            if request.user.features[feature]:
                return view(request, *args, **kwargs)
            messages.warning(request, _("Feature not available"))
            return HttpResponseRedirect("/")

        return require_feature

    return decorator


class FEATURES:
    BOOKKEEPING = "bookkeeping"
    CAMPAIGNS = "campaigns"
    CONTROLLING = "controlling"
    DEALS = "deals"
    FOREIGN_CURRENCIES = "foreign_currencies"
    GLASSFROG = "glassfrog"
    LABOR_COSTS = "labor_costs"
    PLANNING = "planning"
    SKIP_BREAKS = "skip_breaks"
    WORKING_TIME_CORRECTION = "working_time_correction"


bookkeeping_only = feature_required(FEATURES.BOOKKEEPING)
controlling_only = feature_required(FEATURES.CONTROLLING)
deals_only = feature_required(FEATURES.DEALS)
labor_costs_only = feature_required(FEATURES.LABOR_COSTS)


KNOWN_FEATURES = {getattr(FEATURES, attr) for attr in dir(FEATURES) if attr.isupper()}


class UnknownFeature(Exception):
    pass


class UserFeatures:
    def __init__(self, *, email):
        self.email = email

    def __getattr__(self, key):
        try:
            setting = settings.FEATURES[key]
        except KeyError:
            if key not in KNOWN_FEATURES:
                raise UnknownFeature("Unknown feature: %r" % key)

            return False
        if setting is True or setting is False:
            return setting
        return self.email in setting

    __getitem__ = __getattr__
