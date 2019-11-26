from functools import wraps

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _


def permission_required(permission, message=_("Access denied, sorry.")):
    def decorator(view):
        @wraps(view)
        def require_permission(request, *args, **kwargs):
            if request.user.permissions[permission]:
                return view(request, *args, **kwargs)
            messages.warning(request, message)
            return HttpResponseRedirect(request.META.get("HTTP_REFERER") or "/")

        return require_permission

    return decorator


class Permissions:
    BOOK_KEEPING = "book_keeping"


book_keeping_only = permission_required(
    Permissions.BOOK_KEEPING, _("Only book keeping may access this, sorry.")
)
