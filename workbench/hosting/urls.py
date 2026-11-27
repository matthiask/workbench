from django.urls import path

from workbench import generic
from workbench.accounts.features import hosting_only
from workbench.hosting.forms import (
    ServerForm,
    ServerSearchForm,
    SiteContactForm,
    SiteForm,
    SiteSearchForm,
)
from workbench.hosting.models import Server, Site, SiteContact
from workbench.hosting.views import SiteContactDeleteView


urlpatterns = [
    path(
        "",
        hosting_only(
            generic.ListView.as_view(model=Site, search_form_class=SiteSearchForm)
        ),
        name="hosting_site_list",
    ),
    path(
        "autocomplete/",
        hosting_only(
            generic.AutocompleteView.as_view(model=Site, queryset=Site.objects.active())
        ),
        name="hosting_site_autocomplete",
    ),
    path(
        "<int:pk>/",
        hosting_only(generic.DetailView.as_view(model=Site)),
        name="hosting_site_detail",
    ),
    path(
        "create/",
        hosting_only(generic.CreateView.as_view(model=Site, form_class=SiteForm)),
        name="hosting_site_create",
    ),
    path(
        "<int:pk>/update/",
        hosting_only(generic.UpdateView.as_view(model=Site, form_class=SiteForm)),
        name="hosting_site_update",
    ),
    path(
        "<int:pk>/delete/",
        hosting_only(generic.DeleteView.as_view(model=Site)),
        name="hosting_site_delete",
    ),
    path(
        "<int:pk>/add-contact/",
        hosting_only(
            generic.CreateRelatedView.as_view(
                model=SiteContact,
                form_class=SiteContactForm,
                related_model=Site,
            )
        ),
        name="hosting_site_add_contact",
    ),
    path(
        "contacts/<int:pk>/update/",
        hosting_only(
            generic.UpdateView.as_view(
                model=SiteContact,
                form_class=SiteContactForm,
            )
        ),
        name="hosting_sitecontact_update",
    ),
    path(
        "contacts/<int:pk>/delete/",
        hosting_only(
            SiteContactDeleteView.as_view(
                model=SiteContact, template_name="modal_confirm_delete.html"
            )
        ),
        name="hosting_sitecontact_delete",
    ),
    path(
        "servers/",
        hosting_only(
            generic.ListView.as_view(model=Server, search_form_class=ServerSearchForm)
        ),
        name="hosting_server_list",
    ),
    path(
        "servers/<int:pk>/",
        hosting_only(generic.DetailView.as_view(model=Server)),
        name="hosting_server_detail",
    ),
    path(
        "servers/create/",
        hosting_only(generic.CreateView.as_view(model=Server, form_class=ServerForm)),
        name="hosting_server_create",
    ),
    path(
        "servers/<int:pk>/update/",
        hosting_only(generic.UpdateView.as_view(model=Server, form_class=ServerForm)),
        name="hosting_server_update",
    ),
    path(
        "servers/<int:pk>/delete/",
        hosting_only(
            generic.DeleteView.as_view(
                model=Server, template_name="modal_confirm_delete.html"
            )
        ),
        name="hosting_server_delete",
    ),
]
