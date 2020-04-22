import datetime as dt
from functools import total_ordering

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.expressions import RawSQL
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.projects.models import Project, Service
from workbench.tools.formats import local_date_format
from workbench.tools.models import ModelWithTotal, SearchQuerySet, Z
from workbench.tools.urls import model_urls


class OfferQuerySet(SearchQuerySet):
    def in_preparation_choices(self, *, include=None):
        offers = {True: [], False: []}
        for offer in self.filter(Q(status=Offer.IN_PREPARATION) | Q(pk=include)):
            offers[offer.id == include].append((offer.pk, offer))
        return (
            [("", "----------")] + offers[True] + [(_("In preparation"), offers[False])]
        )

    def maybe_actionable(self, *, user):
        return self.filter(
            Q(status__lt=Offer.ACCEPTED),
            Q(owned_by=user) | Q(owned_by__is_active=False),
        ).select_related("project", "owned_by")

    def offered(self):
        return self.filter(status=Offer.OFFERED)

    def accepted(self):
        return self.filter(status=Offer.ACCEPTED)

    def sr(self):
        return self.select_related("owned_by", "project")


@model_urls
@total_ordering
class Offer(ModelWithTotal):
    IN_PREPARATION = 10
    OFFERED = 20
    ACCEPTED = 30
    DECLINED = 40

    STATUS_CHOICES = (
        (IN_PREPARATION, _("In preparation")),
        (OFFERED, _("Offered")),
        (ACCEPTED, _("Accepted")),
        (DECLINED, _("Declined")),
    )

    created_at = models.DateTimeField(_("created at"), default=timezone.now)
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_("project"),
        related_name="offers",
    )

    offered_on = models.DateField(_("offered on"), blank=True, null=True)
    closed_on = models.DateField(_("closed on"), blank=True, null=True)

    title = models.CharField(_("title"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    owned_by = models.ForeignKey(
        User, on_delete=models.PROTECT, verbose_name=_("responsible")
    )

    status = models.PositiveIntegerField(
        _("status"), choices=STATUS_CHOICES, default=IN_PREPARATION
    )

    postal_address = models.TextField(_("postal address"))
    _code = models.IntegerField(_("code"))

    objects = OfferQuerySet.as_manager()

    class Meta:
        ordering = ["-pk"]
        verbose_name = _("offer")
        verbose_name_plural = _("offers")

    def __str__(self):
        return "{} {} - {}".format(
            self.code, self.title, self.owned_by.get_short_name()
        )

    def __html__(self):
        return format_html(
            "<small>{}</small> {} - {}",
            self.code,
            self.title,
            self.owned_by.get_short_name(),
        )

    def __lt__(self, other):
        # Sorting:
        # - Declined offers are at the end
        # - None (not offered yet) is between declined and other offers
        # - Else order by _code
        myself = (self.is_declined, True, self._code)
        if other is None:
            return myself < (False, True, 1e100)
        elif isinstance(other, Offer):
            return myself < (other.is_declined, True, other._code)
        else:
            return 1

    def get_absolute_url(self):
        return "%s#offer%s" % (self.project.get_absolute_url(), self.pk)

    def save(self, *args, **kwargs):
        new = False
        if not self.pk:
            self._code = RawSQL(
                "SELECT COALESCE(MAX(_code), 0) + 1 FROM offers_offer"
                " WHERE project_id = %s",
                (self.project_id,),
            )
            new = True
        super().save(*args, **kwargs)
        if new:
            self.refresh_from_db()

    save.alters_data = True

    @property
    def code(self):
        return "%s-o%02d" % (self.project.code, self._code)

    def _calculate_total(self):
        self.subtotal = sum(
            (
                service.service_cost
                for service in self.services.all()
                if not service.is_optional
            ),
            Z,
        )
        super()._calculate_total()

    def clean(self):
        super().clean()

        if self.status in (self.OFFERED, self.ACCEPTED, self.DECLINED):
            if not self.offered_on:
                raise ValidationError(
                    {"status": _("Offered on date missing for selected state.")}
                )

        if self.status >= self.ACCEPTED and not self.closed_on:
            self.closed_on = dt.date.today()
        elif self.status < self.ACCEPTED and self.closed_on:
            self.closed_on = None

    @property
    def pretty_status(self):
        if self.status == self.IN_PREPARATION:
            return _("In preparation since %(created_at)s") % {
                "created_at": local_date_format(self.created_at.date())
            }
        elif self.status == self.OFFERED:
            if self.project.closed_on:
                return _(
                    "Offered on %(offered_on)s, but project closed on %(closed_on)s"
                ) % {
                    "offered_on": local_date_format(self.offered_on),
                    "closed_on": local_date_format(self.project.closed_on),
                }

            return _("Offered on %(offered_on)s") % {
                "offered_on": local_date_format(self.offered_on)
            }
        elif self.status in (self.ACCEPTED, self.DECLINED):
            return _("%(status)s on %(closed_on)s") % {
                "status": self.get_status_display(),
                "closed_on": local_date_format(self.closed_on),
            }
        return self.get_status_display()

    @property
    def status_badge(self):
        if self.status == self.OFFERED and self.project.closed_on:
            css = "warning"
        else:
            css = {
                self.IN_PREPARATION: "info",
                self.OFFERED: "success",
                self.ACCEPTED: "default",
                self.DECLINED: "danger",
            }[self.status]

        return format_html(
            '<span class="badge badge-{}">{}</span>', css, self.pretty_status
        )

    @property
    def total_title(self):
        return _("total CHF incl. tax") if self.liable_to_vat else _("total CHF")

    @classmethod
    def allow_create(cls, request):
        if request.path == reverse("offers_offer_create"):
            messages.error(
                request,
                _(
                    "Offers can only be created from projects. Go to the project"
                    " and add services first, then you'll be able to create the"
                    " offer itself."
                ),
            )
            return False
        return True

    @property
    def is_declined(self):
        return self.status == self.DECLINED

    def copy_to(self, *, project, owned_by):
        offer = Offer.objects.create(
            project=project,
            title=self.title,
            description=self.description,
            owned_by=owned_by,
            discount=self.discount,
            liable_to_vat=self.liable_to_vat,
            show_service_details=self.show_service_details,
        )
        for service in self.services.all():
            new = Service(
                project=project,
                offer=offer,
                allow_logging=service.allow_logging,
                is_optional=service.is_optional,
                role=service.role,
                title=service.title,
                description=service.description,
                position=service.position,
                effort_type=service.effort_type,
                effort_hours=service.effort_hours,
                effort_rate=service.effort_rate,
                cost=service.cost,
                third_party_costs=service.third_party_costs,
            )
            new.save(skip_related_model=True)
        offer.save()
        return offer
