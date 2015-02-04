from django.db import models

from tools.search import search


class SearchQuerySet(models.QuerySet):
    def search(self, terms):
        return search(self, terms)


SearchManager = models.Manager.from_queryset(SearchQuerySet)
