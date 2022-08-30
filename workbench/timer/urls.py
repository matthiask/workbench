from django.shortcuts import render
from django.urls import path, re_path

from workbench.timer import views


urlpatterns = [
    path("timer/", views.timer, name="timer"),
    path("timestamps/", views.timestamps, name="timestamps"),
    path("create-timestamp/", views.create_timestamp, name="create_timestamp"),
    path("list-timestamps/", views.list_timestamps, name="list_timestamps"),
    re_path(
        r"^delete-timestamp/([0-9]+)/$", views.delete_timestamp, name="delete_timestamp"
    ),
    path(
        "timestamps-controller/",
        render,
        {"template_name": "timestamps-controller.html"},
        name="timestamps-controller",
    ),
]
