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
    BOOK_KEEPING = "book_keeping"
    GLASSFROG = "glassfrog"


book_keeping_only = feature_required(
    FEATURES.BOOK_KEEPING, _("Only book keeping may access this, sorry.")
)
