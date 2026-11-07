from django.contrib import messages
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.prefetch import GenericPrefetch
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from workbench.accounts.features import FEATURES
from workbench.accounts.models import User
from workbench.deals.models import Deal
from workbench.invoices.models import Invoice, RecurringInvoice
from workbench.projects.models import Project
from workbench.tools.models import Model, SearchQuerySet
from workbench.tools.urls import model_urls


# Notes are shown on these objects in the web interface, with the features
# they require (None: everyone)
TARGETS = {
    "deal": (Deal, FEATURES.DEALS),
    "invoice": (Invoice, FEATURES.CONTROLLING),
    "recurring_invoice": (RecurringInvoice, FEATURES.CONTROLLING),
    "project": (Project, None),
}


def visible_content_types(user):
    """Content types of the objects whose notes the user may see"""
    return {
        ContentType.objects.get_for_model(model).pk: key
        for key, (model, feature) in TARGETS.items()
        if feature is None or user.features[feature]
    }


class NoteQuerySet(SearchQuerySet):
    def visible(self, types):
        """Notes of existing objects of the given content types (see
        ``visible_content_types()``); deleting objects doesn't delete their
        notes"""
        q = Q(pk__in=[])
        for content_type, key in types.items():
            q |= Q(
                content_type=content_type,
                object_id__in=TARGETS[key][0].objects.values("pk"),
            )
        return self.filter(q)

    def with_content_objects(self):
        # Their names include their owner, invoice codes the project's
        return self.prefetch_related(
            GenericPrefetch(
                "content_object",
                [
                    Deal.objects.select_related("owned_by"),
                    Invoice.objects.select_related("owned_by", "project"),
                    RecurringInvoice.objects.select_related("owned_by"),
                    Project.objects.select_related("owned_by"),
                ],
            )
        )

    def for_content_object(self, content_object):
        return self.filter(
            content_type=ContentType.objects.get_for_model(content_object),
            object_id=content_object.pk,
        )


@model_urls
class Note(Model):
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("created by"),
        related_name="notes",
    )
    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"))

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, related_name="+"
    )
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    objects = NoteQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("note")
        verbose_name_plural = pgettext_lazy("notes feature", "notes")

    def __str__(self):
        return f"{self.title} - {self.content_type.name} {self.object_id} - {self.created_by.get_short_name()}"

    @classmethod
    def allow_update(cls, instance, request):
        # Like the notes list and the notes API
        if instance.content_type_id not in visible_content_types(request.user):
            messages.error(request, _("You are not permitted to edit this note."))
            return False
        return True

    allow_delete = allow_update

    def get_absolute_url(self):
        model = self.content_type.model_class()
        viewname = f"{model._meta.app_label}_{model._meta.model_name}_detail"
        return f"{reverse(viewname, kwargs={'pk': self.object_id})}#note-{self.pk}"
