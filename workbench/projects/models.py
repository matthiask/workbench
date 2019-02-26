from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.db.models.expressions import RawSQL
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _, ugettext

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.tools.models import SearchQuerySet, Model
from workbench.tools.urls import model_urls


class ProjectQuerySet(SearchQuerySet):
    pass


@model_urls()
class Project(Model):
    ACQUISITION = 10
    WORK_IN_PROGRESS = 20
    FINISHED = 30
    DECLINED = 40

    STATUS_CHOICES = (
        (ACQUISITION, _("Acquisition")),
        (WORK_IN_PROGRESS, _("Work in progress")),
        (FINISHED, _("Finished")),
        (DECLINED, _("Declined")),
    )

    customer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        verbose_name=_("customer"),
        related_name="+",
    )
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_("contact"),
        related_name="+",
    )

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("owned by"), related_name="+"
    )

    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=ACQUISITION
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    invoicing = models.BooleanField(
        _("invoicing"),
        default=True,
        help_text=_("This project is eligible for invoicing."),
    )
    maintenance = models.BooleanField(
        _("maintenance"),
        default=False,
        help_text=_("This project is used for maintenance work."),
    )

    _code = models.IntegerField(_("code"))

    objects = models.Manager.from_queryset(ProjectQuerySet)()

    class Meta:
        ordering = ("-id",)
        verbose_name = _("project")
        verbose_name_plural = _("projects")

    def __str__(self):
        return self.title

    def __html__(self):
        return format_html("<small>{}</small> {}", self.code, self.title)

    @property
    def code(self):
        return "%s-%04d" % (self.created_at.year, self._code)

    def save(self, *args, **kwargs):
        if not self.pk:
            self._code = RawSQL(
                "SELECT COALESCE(MAX(_code), 0) + 1 FROM projects_project"
                " WHERE EXTRACT(year FROM created_at) = %s",
                (timezone.now().year,),
            )
        super().save(*args, **kwargs)

    save.alters_data = True

    def status_css(self):
        return {
            self.ACQUISITION: "info",
            self.WORK_IN_PROGRESS: "success",
            self.FINISHED: "default",
            self.DECLINED: "warning",
        }[self.status]

    @cached_property
    def overview(self):
        # Avoid circular imports
        from workbench.logbook.models import LoggedHours
        from workbench.offers.models import Service

        return {
            "logged": LoggedHours.objects.filter(service__offer__project=self)
            .order_by()
            .aggregate(h=Sum("hours"))["h"]
            or Decimal(),
            "approved": sum(
                (
                    service.approved_hours
                    for service in Service.objects.filter(offer__project=self)
                ),
                Decimal(),
            ),
        }

    def pretty_status(self):
        parts = [self.get_status_display()]
        if not self.invoicing:
            parts.append(ugettext("no invoicing"))
        if self.maintenance:
            parts.append(ugettext("maintenance"))
        return ", ".join(parts)

    @property
    def services(self):
        from workbench.offers.models import Service

        # TODO service archival?
        return Service.objects.filter(offer__project=self)
