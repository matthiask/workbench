from django.core.exceptions import PermissionDenied
from django.db import models

from tools.deletion import related_classes
from tools.search import search


class SearchQuerySet(models.QuerySet):
    def search(self, terms):
        return search(self, terms)


SearchManager = models.Manager.from_queryset(SearchQuerySet)


def safe_queryset_and(head, *tail):
    """
    Safe AND-ing of querysets. If one of both queries has its
    DISTINCT flag set, sets distinct on both querysets. Also takes extra
    care to preserve the result of the following queryset methods:

    * ``reverse()``
    * ``transform()``
    * ``select_related()``
    * ``prefetch_related()``
    """

    def _merge(qs1, qs2):
        if qs1.query.distinct or qs2.query.distinct:
            res = qs1.distinct() & qs2.distinct()
        else:
            res = qs1 & qs2

        res._transform_fns = list(set(
            getattr(qs1, '_transform_fns', []) +
            getattr(qs2, '_transform_fns', [])))

        if not (qs1.query.standard_ordering and qs2.query.standard_ordering):
            res.query.standard_ordering = False

        select_related = [qs1.query.select_related, qs2.query.select_related]
        if False in select_related:
            # We are not interested in the default value
            select_related.remove(False)

        if len(select_related) == 1:
            res.query.select_related = select_related[0]
        elif len(select_related) == 2:
            if True in select_related:
                # Prefer explicit select_related to generic select_related()
                select_related.remove(True)

            if len(select_related) > 0:
                # If we have two explicit select_related calls, take any
                res.query.select_related = select_related[0]
            else:
                res = res.select_related()

        res._prefetch_related_lookups = list(
            set(qs1._prefetch_related_lookups) |
            set(qs2._prefetch_related_lookups))

        return res

    while tail:
        head = _merge(head, tail[0])
        tail = tail[1:]
    return head


class ProtectRelationsModel(models.Model):
    def delete(self, *args, **kwargs):
        rel = related_classes(self)
        if rel > {self.__class__}:
            raise PermissionDenied(
                'Deleting %s with related objects is not allowed (%s)' % (
                    self._meta.verbose_name_plural,
                    rel,
                ))
        super().delete(*args, **kwargs)
    delete.alters_data = True
