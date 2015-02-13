from django.conf.urls import patterns, url, include

from accounts import views


urlpatterns = patterns(
    '',
    url(
        r'^update/$',
        views.UserUpdateView.as_view(),
        name='accounts_update'),
    url(r'', include('django.contrib.auth.urls')),
)
