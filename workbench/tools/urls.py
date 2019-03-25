from django.urls import NoReverseMatch, reverse


class _MUHelper:
    def __init__(self, viewname_pattern, kwargs):
        self.viewname_pattern = viewname_pattern
        self.kwargs = kwargs

    def url(self, item):
        try:
            return reverse(self.viewname_pattern % item)
        except NoReverseMatch:
            return reverse(self.viewname_pattern % item, **self.kwargs)

    __getitem__ = url


class _Descriptor:
    def __get__(self, obj, objtype=None):
        viewname_pattern = "%s_%s_%%s" % (obj._meta.app_label, obj._meta.model_name)
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
