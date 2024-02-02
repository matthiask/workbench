from django.urls import path

from . import views


urlpatterns = [
    path("", views.accounts, name="accounts"),
    path("update/", views.UserUpdateView.as_view(), name="accounts_update"),
    path("login/", views.login, name="login"),
    path("oauth2/", views.oauth2, name="accounts_oauth2"),
    path("logout/", views.logout, name="logout"),
]
