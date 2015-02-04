from collections import defaultdict

from django.shortcuts import get_object_or_404, render

from deals.models import Funnel, Deal


def funnel_detail(request, pk):
    funnel = get_object_or_404(Funnel, pk=pk)

    deals = defaultdict(list)
    for deal in funnel.deals.all():
        deals[deal.status].append(deal)

    return render(request, 'deals/funnel_detail.html', {
        'funnel': funnel,
        'funnel_details': [
            {
                'title': title,
                'deals': deals.get(status, []),
            } for status, title in Deal.STATUS_CHOICES
        ],
    })
