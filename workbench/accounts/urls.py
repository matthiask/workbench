from django.urls import re_path

from . import views


urlpatterns = [
    re_path(r"^accounts/$", views.accounts, name="accounts"),
    re_path(
        r"^accounts/update/$", views.UserUpdateView.as_view(), name="accounts_update"
    ),
    re_path(r"^accounts/login/$", views.login, name="login"),
    re_path(r"^accounts/oauth2/$", views.oauth2, name="accounts_oauth2"),
    re_path(r"^accounts/logout/$", views.logout, name="logout"),
    #
    re_path(r"^profile/$", views.profile, name="profile"),
    re_path(r"^profile/(?P<pk>[0-9]+)/$", views.profile, name="profile"),
]
