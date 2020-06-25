from contextlib import suppress

from django.urls import NoReverseMatch, reverse


class _MUHelper:
    def __init__(self, viewname_pattern, kwargs):
        self.viewname_pattern = viewname_pattern
        self.kwargs = kwargs

    def __getitem__(self, item):
        viewname = self.viewname_pattern.format(item)
        if self.kwargs:
            with suppress(NoReverseMatch):
                return reverse(viewname, **self.kwargs)
        return reverse(viewname)


class _Descriptor:
    def __init__(self, viewname_pattern):
        self.viewname_pattern = viewname_pattern

    def __get__(self, obj, objtype=None):
        if not obj:
            return _MUHelper(self.viewname_pattern, {})
        kwargs = {"kwargs": {"pk": obj.pk}}
        helper = obj.__dict__["urls"] = _MUHelper(self.viewname_pattern, kwargs)
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

    cls.urls = _Descriptor(
        viewname_pattern="{}_{}_{{}}".format(cls._meta.app_label, cls._meta.model_name)
    )
    if not hasattr(cls, "get_absolute_url"):
        cls.get_absolute_url = lambda self: self.urls["detail"]
    return cls
