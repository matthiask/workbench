from django.urls import NoReverseMatch, reverse


class _MUHelper(object):
    def __init__(self, viewname_pattern, kwargs):
        self.viewname_pattern = viewname_pattern
        self.kwargs = kwargs

    def __getitem__(self, item):
        return self.url(item)

    def url(self, item, **kwargs):
        kw = self.kwargs
        if kwargs:
            kw = kw.copy()
            kw["kwargs"].update(kwargs)

        try:
            return reverse(self.viewname_pattern % item, **kw)
        except NoReverseMatch as e:
            try:
                return reverse(self.viewname_pattern % item)
            except NoReverseMatch:
                # Re-raise exception with kwargs; it's more informative
                raise e


def model_urls(reverse_kwargs_fn=lambda object: {"pk": object.pk}, default="detail"):
    """
    Usage::

        @model_urls()
        class MyModel(models.Model):
            pass

        instance = MyModel.objects.get(...)
        instance.urls.url('detail') == instance.get_absolute_url()
    """

    def _dec(cls):
        class _descriptor(object):
            def __get__(self, obj, objtype=None):
                viewname_pattern = "%s_%s_%%s" % (
                    obj._meta.app_label,
                    obj._meta.model_name,
                )
                kwargs = {"kwargs": reverse_kwargs_fn(obj)}
                helper = obj.__dict__["urls"] = _MUHelper(viewname_pattern, kwargs)
                return helper

        cls.urls = _descriptor()
        cls.get_absolute_url = lambda self: self.urls.url(default)
        return cls

    return _dec


def tryreverse(*args, **kwargs):
    """
    Calls ``django.urls.reverse``, and returns ``None`` on
    failure instead of raising an exception.
    """
    try:
        return reverse(*args, **kwargs)
    except NoReverseMatch:
        return None
