from django.shortcuts import render

from contacts.models import Organization, Person
from deals.models import Deal
from projects.models import Project


def search(request):
    q = request.GET.get('q')

    return render(request, 'search.html', {
        'search': {
            'query': q,
            'results': [(
                model._meta.verbose_name_plural,
                model.objects.search(q),
            ) for model in (
                Organization,
                Person,
                Project,
                Deal,
            )],
        },
    })
