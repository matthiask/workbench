from django.urls import re_path

from workbench.notes import views


app_name = "notes"
urlpatterns = [re_path(r"^add-note/$", views.add_note, name="add")]
