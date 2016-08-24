from django.utils.deprecation import MiddlewareMixin

from debug_toolbar.middleware import DebugToolbarMiddleware


class WorkingDebugToolbarMiddleware(MiddlewareMixin, DebugToolbarMiddleware):
    pass
