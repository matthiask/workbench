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
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")

        return require_feature

    return decorator


class FEATURES:
    BOOKKEEPING = "bookkeeping"
    CONTROLLING = "controlling"
    FOREIGN_CURRENCIES = "foreign_currencies"
    GLASSFROG = "glassfrog"
    LABOR_COSTS = "labor_costs"
    TIMESTAMPS = "timestamps"


bookkeeping_only = feature_required(
    FEATURES.BOOKKEEPING, _("Only bookkeeping may access this, sorry.")
)
controlling_only = feature_required(
    FEATURES.CONTROLLING, _("Only controlling may access this, sorry.")
)
labor_costs_only = feature_required(
    FEATURES.LABOR_COSTS, _("Only labor costs may access this, sorry.")
)


KNOWN_FEATURES = {getattr(FEATURES, attr) for attr in dir(FEATURES) if attr.isupper()}


class UnknownFeature(Exception):
    pass
