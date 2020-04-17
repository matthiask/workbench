from django.shortcuts import render
from django.urls import re_path

from workbench.timer import views


urlpatterns = [
    re_path(r"^timer/$", views.timer, name="timer"),
    re_path(r"^timestamps/$", views.timestamps, name="timestamps"),
    re_path(r"^create-timestamp/$", views.create_timestamp, name="create_timestamp"),
    re_path(r"^list-timestamps/$", views.list_timestamps, name="list_timestamps"),
    re_path(
        r"^delete-timestamp/([0-9]+)/$", views.delete_timestamp, name="delete_timestamp"
    ),
    re_path(
        r"^timestamps-controller/$",
        render,
        {"template_name": "timestamps-controller.html"},
        name="timestamps-controller",
    ),
]
