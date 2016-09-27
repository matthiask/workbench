from django.conf.urls import url

from logbook.forms import LoggedHoursSearchForm
from logbook.models import LoggedHours

from tools.views import ListView, DetailView, MessageView


urlpatterns = [
    url(
        r'^$',
        ListView.as_view(
            model=LoggedHours,
            search_form_class=LoggedHoursSearchForm,
            show_create_button=False,
        ),
        name='logbook_loggedhours_list'),
    url(
        r'^(?P<pk>\d+)/$',
        DetailView.as_view(
            model=LoggedHours,
        ),
        name='logbook_loggedhours_detail'),
    url(
        r'^(?P<pk>\d+)/update/$',
        MessageView.as_view(
            redirect_to='logbook_loggedhours_list',
            message='Not implemented yet.',
        ),
        name='logbook_loggedhours_update'),
    url(
        r'^(?P<pk>\d+)/delete/$',
        MessageView.as_view(
            redirect_to='logbook_loggedhours_list',
            message='Not implemented yet.',
        ),
        name='logbook_loggedhours_delete'),
]
