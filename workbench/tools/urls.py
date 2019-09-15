from contextlib import suppress

from django.urls import NoReverseMatch, reverse


class _MUHelper:
    def __init__(self, viewname_pattern, kwargs):
        self.viewname_pattern = viewname_pattern
        self.kwargs = kwargs

    def __getitem__(self, item):
        if self.kwargs:
            with suppress(NoReverseMatch):
                return reverse(self.viewname_pattern % item, **self.kwargs)
        return reverse(self.viewname_pattern % item)


class _Descriptor:
    def __get__(self, obj, objtype=None):
        info = obj._meta if obj else objtype._meta
        viewname_pattern = "%s_%s_%%s" % (info.app_label, info.model_name)
        if not obj:
            return _MUHelper(viewname_pattern, {})
        kwargs = {"kwargs": {"pk": obj.pk}}
        helper = obj.__dict__["urls"] = _MUHelper(viewname_pattern, kwargs)
        return helper


def model_urls(cls):
    """
    Usage::

        @model_urls
        class MyModel(models.Model):
            pass

        instance = MyModel.objects.get(...)
        instance.urls["detail"] == instance.get_absolute_url()
    """

    cls.urls = _Descriptor()
    if not hasattr(cls, "get_absolute_url"):
        cls.get_absolute_url = lambda self: self.urls["detail"]
    return cls
