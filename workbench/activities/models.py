from datetime import date, timedelta

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Person
from workbench.deals.models import Deal
from workbench.projects.models import Project
from workbench.tools.formats import local_date_format, pretty_due
from workbench.tools.models import Model, SearchQuerySet
from workbench.tools.urls import model_urls


class ActivityQuerySet(SearchQuerySet):
    def open(self):
        return self.filter(completed_at__isnull=True).select_related(
            "contact__organization", "project", "deal", "owned_by"
        )


@model_urls
class Activity(Model):
    contact = models.ForeignKey(
        Person,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("contact"),
        related_name="activities",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("project"),
        related_name="activities",
    )
    deal = models.ForeignKey(
        Deal,
        on_delete=models.PROTECT,
        verbose_name=_("deal"),
        blank=True,
        null=True,
        related_name="activities",
    )
    title = models.CharField(_("title"), max_length=200)
    notes = models.TextField(_("notes"), blank=True)
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("responsible"),
        related_name="activities",
    )
    due_on = models.DateField(_("due on"), blank=True, null=True)
    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    completed_at = models.DateTimeField(_("completed at"), blank=True, null=True)

    objects = ActivityQuerySet.as_manager()

    class Meta:
        ordering = ("due_on",)
        verbose_name = _("activity")
        verbose_name_plural = _("activities")

    def __str__(self):
        return self.title

    def context(self):
        return [c for c in [self.contact, self.deal, self.project] if c]

    @property
    def pretty_status(self):
        if self.completed_at:
            return _("completed on %(completed_on)s") % {
                "completed_on": local_date_format(self.completed_at.date())
            }

        if self.due_on:
            return "%s (%s)" % (pretty_due(self.due_on), local_date_format(self.due_on))

        return _("open")

    @property
    def status_css(self):
        if self.completed_at:
            return "default"
        if self.due_on:
            if self.due_on < date.today():
                return "danger"
            elif self.due_on < date.today() + timedelta(days=3):
                return "warning"
        return "info"

    @classmethod
    def get_redirect_url(cls, instance, request):
        if not request.is_ajax():
            return cls().urls["list"]
