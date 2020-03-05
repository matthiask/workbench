from functools import wraps

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _


def feature_required(feature, message=_("Access denied, sorry.")):
    def decorator(view):
        @wraps(view)
        def require_feature(request, *args, **kwargs):
            if request.user.features[feature]:
                return view(request, *args, **kwargs)
            messages.warning(request, message)
            return HttpResponseRedirect("/")

        return require_feature

    return decorator


class FEATURES:
    BOOKKEEPING = "bookkeeping"
    CONTROLLING = "controlling"
    DEALS = "deals"
    FOREIGN_CURRENCIES = "foreign_currencies"
    GLASSFROG = "glassfrog"
    LABOR_COSTS = "labor_costs"


bookkeeping_only = feature_required(
    FEATURES.BOOKKEEPING, _("Only bookkeeping may access this, sorry.")
)
controlling_only = feature_required(FEATURES.CONTROLLING)
deals_only = feature_required(FEATURES.DEALS)
labor_costs_only = feature_required(FEATURES.LABOR_COSTS)


KNOWN_FEATURES = {getattr(FEATURES, attr) for attr in dir(FEATURES) if attr.isupper()}


class UnknownFeature(Exception):
    pass
