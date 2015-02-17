from django.conf.urls import patterns, url, include
from django.contrib.auth.decorators import login_required

from accounts import views


urlpatterns = patterns(
    '',
    url(
        r'^update/$',
        login_required(views.UserUpdateView.as_view()),
        name='accounts_update'),
    url(r'', include('django.contrib.auth.urls')),

    url(
        r'^oauth2/start/$',
        views.oauth2_start,
        name='accounts_oauth2_start'),
    url(
        r'^oauth2/end/$',
        views.oauth2_end,
        name='accounts_oauth2_end'),
)
