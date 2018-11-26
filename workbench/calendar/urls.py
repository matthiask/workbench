from django.conf.urls import url
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import ugettext_lazy as _

from workbench import generic

from .forms import DayForm, DaySearchForm, PresenceForm
from .models import App, Day, activate_app, current_app
from . import views


def app_mixin(view):
    class View(view):
        def dispatch(self, request, *args, **kwargs):
            app = kwargs.get("app")
            if app:
                self.app = get_object_or_404(App, users=request.user, slug=app)
            with activate_app(self.app.slug):
                response = super().dispatch(request, *args, **kwargs)
                if hasattr(response, "render"):
                    # Have to render responses inside the activate_app block.
                    response.render()
                return response

        def get_root_queryset(self):
            return super().get_root_queryset().filter(app=self.app)

    return View


list_url = reverse_lazy("calendar_day_list", kwargs={"app": current_app})


urlpatterns = [
    url(
        r"^(?P<app>\w+)/$",
        app_mixin(generic.ListView).as_view(
            model=Day,
            search_form_class=DaySearchForm,
            paginate_by=None,
            show_search_field=False,
            show_create_button=False,
        ),
        name="calendar_day_list",
    ),
    url(
        r"^(?P<app>\w+)/(?P<pk>[0-9]+)/$",
        app_mixin(generic.DetailView).as_view(model=Day),
        name="calendar_day_detail",
    ),
    url(
        r"^(?P<app>\w+)/create/$",
        app_mixin(generic.MessageView).as_view(
            redirect_to=list_url,
            message=_("Creating days is not supported."),
            level=messages.WARNING,
        ),
        name="calendar_day_create",
    ),
    url(
        r"^(?P<app>\w+)/(?P<pk>[0-9]+)/update/$",
        app_mixin(generic.UpdateView).as_view(
            model=Day, form_class=DayForm, success_url=list_url
        ),
        name="calendar_day_update",
    ),
    url(
        r"^(?P<app>\w+)/(?P<pk>[0-9]+)/delete/$",
        app_mixin(generic.MessageView).as_view(
            redirect_to=list_url,
            message=_("Deleting days is not supported."),
            level=messages.WARNING,
        ),
        name="calendar_day_delete",
    ),
    url(
        r"^(?P<app>\w+)/update/$",
        staff_member_required(
            app_mixin(generic.UpdateView).as_view(
                model=App,
                form_class=PresenceForm,
                lookup_field="slug",
                lookup_url_kwarg="app",
                success_url="/",
            )
        ),
        name="calendar_app_update",
    ),
    url(r"^(?P<code>[^/]+)/hangar\.ics$", views.ics, name="calendar_ics"),
]
