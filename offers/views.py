from offers.forms import OfferSearchForm
from offers.models import Offer
from tools.views import ListView


class OfferListView(ListView):
    model = Offer
    search_form_class = OfferSearchForm

    def get_queryset(self):
        return super().get_queryset().select_related(
            'customer',
            'contact__organization',
        )
