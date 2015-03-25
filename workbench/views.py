from django.contrib import messages
from django.shortcuts import render
from django.utils.translation import ugettext as _

from contacts.models import Organization, Person
from deals.models import Deal
from offers.models import Offer
from projects.models import Project


def search(request):
    results = []
    q = request.GET.get('q', '')
    if q:
        results = [(
            model._meta.verbose_name_plural,
            model.objects.search(q),
        ) for model in (
            Organization,
            Person,
            Project,
            Deal,
            Offer,
        )]
    else:
        messages.error(request, _('Search query missing.'))

    return render(request, 'search.html', {
        'search': {
            'query': q,
            'results': results,
        },
    })
