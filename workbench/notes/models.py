from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.tools.models import Model, SearchQuerySet
from workbench.tools.urls import model_urls


class NoteQuerySet(SearchQuerySet):
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
        verbose_name_plural = _("notes")

    def __str__(self):
        return "{} - {} {} - {}".format(
            self.title,
            self.content_type.name,
            self.object_id,
            self.created_by.get_short_name(),
        )

    def get_absolute_url(self):
        model = self.content_type.model_class()
        viewname = "%s_%s_detail" % (model._meta.app_label, model._meta.model_name)
        return reverse(viewname, kwargs={"pk": self.object_id})
