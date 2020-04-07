from django.conf.urls import url

from . import views


urlpatterns = [
    url(r"^accounts/$", views.accounts, name="accounts"),
    url(r"^accounts/update/$", views.UserUpdateView.as_view(), name="accounts_update"),
    url(r"^accounts/login/$", views.login, name="login"),
    url(r"^accounts/oauth2/$", views.oauth2, name="accounts_oauth2"),
    url(r"^accounts/logout/$", views.logout, name="logout"),
    #
    url(r"^profile/$", views.profile, name="profile"),
    url(r"^profile/(?P<pk>[0-9]+)/$", views.profile, name="profile"),
]
