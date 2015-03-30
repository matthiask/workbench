from activities.forms import ActivitySearchForm
from activities.models import Activity
from tools.views import ListView


class ActivityListView(ListView):
    model = Activity
    search_form_class = ActivitySearchForm

    def get_queryset(self):
        return super().get_queryset().select_related(
            'project',
            'deal',
            'contact',
            'owned_by',
        )
