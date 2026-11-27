import datetime as dt

from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils.translation import gettext_lazy as _

from workbench.accounts.models import User
from workbench.contacts.models import Organization, Person
from workbench.tools.models import Model, SearchQuerySet
from workbench.tools.urls import model_urls


@model_urls
class Server(Model):
    title = models.CharField(_("title"), max_length=100, unique=True)
    notes = models.TextField(_("notes"), blank=True)
    is_archived = models.BooleanField(_("is archived"), default=False)

    class Meta:
        ordering = ["is_archived", "title"]
        verbose_name = _("server")
        verbose_name_plural = _("servers")

    def __str__(self):
        return self.title

    def active_sites(self):
        return self.sites.active().with_problem_flags().select_related("customer")

    def outage_contacts(self):
        """The active people to contact about outages and maintenance of the
        server's active sites, with the titles of their sites"""
        contacts = (
            SiteContact.objects
            .filter(
                role=SiteContact.OUTAGE,
                site__server=self,
                site__is_archived=False,
                person__is_archived=False,
            )
            .select_related("site", "person__organization")
            .prefetch_related("person__emailaddresses", "person__phonenumbers")
            .order_by("person__given_name", "person__family_name", "site__title")
        )
        people = {}
        for contact in contacts:
            person = people.setdefault(contact.person.pk, contact.person)
            person.site_titles = [*getattr(person, "site_titles", []), contact.site]
            person.email = next(
                (email.email for email in person.emailaddresses.all()), ""
            )
        return list(people.values())


class SiteQuerySet(SearchQuerySet):
    def search(self, terms):
        queryset = self
        for term in terms.split():
            queryset = queryset.filter(
                Q(title__icontains=term)
                | Q(domains__icontains=term)
                | Q(customer__name__icontains=term)
                | Q(server__title__iexact=term)
            )
        return queryset

    def active(self):
        return self.filter(is_archived=False)

    def with_problem_flags(self):
        from workbench.invoices.models import RecurringInvoice

        return self.annotate(
            has_running_invoice=Exists(
                RecurringInvoice.objects.filter(
                    Q(ends_on__isnull=True) | Q(ends_on__gte=dt.date.today()),
                    site=OuterRef("pk"),
                )
            ),
            has_outage_contact=Exists(
                SiteContact.objects.filter(
                    site=OuterRef("pk"),
                    role=SiteContact.OUTAGE,
                    person__is_archived=False,
                )
            ),
        )

    def with_problems(self):
        return (
            self
            .active()
            .with_problem_flags()
            .filter(
                Q(has_running_invoice=False, no_invoice_reason="")
                | Q(has_outage_contact=False)
            )
        )


@model_urls
class Site(Model):
    title = models.CharField(
        _("title"), max_length=200, help_text=_("The main domain of the site.")
    )
    domains = models.TextField(
        _("further domains"),
        blank=True,
        help_text=_("One host name per line."),
    )
    server = models.ForeignKey(
        Server,
        on_delete=models.PROTECT,
        verbose_name=_("server"),
        related_name="sites",
    )
    customer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        verbose_name=_("customer"),
        related_name="sites",
    )
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_("responsible"),
        related_name="+",
    )
    password_manager_url = models.URLField(
        _("password manager"),
        max_length=1000,
        blank=True,
        help_text=_("Link to the credentials, never the credentials themselves."),
    )
    no_invoice_reason = models.CharField(
        _("reason without recurring invoice"),
        max_length=200,
        blank=True,
        help_text=_("For example a maintenance contract or an internal site."),
    )
    notes = models.TextField(_("notes"), blank=True)
    is_archived = models.BooleanField(_("is archived"), default=False)

    objects = SiteQuerySet.as_manager()

    class Meta:
        ordering = ["title"]
        verbose_name = _("site")
        verbose_name_plural = _("sites")

    def __str__(self):
        return self.title

    def host_names(self):
        """The title and the further domains, lowercased"""
        return [
            name.strip().lower()
            for name in [self.title, *self.domains.splitlines()]
            if name.strip()
        ]

    def running_invoices(self):
        return [
            invoice
            for invoice in self.recurringinvoices.all()
            if not invoice.ends_on or invoice.ends_on >= dt.date.today()
        ]

    PROBLEMS = {
        "no_recurring_invoice": _("No recurring invoice"),
        "no_outage_contact": _("No contact for outages"),
    }

    def problem_keys(self):
        """What's missing on an active site; uses the flags of
        ``with_problem_flags()`` when annotated"""
        if self.is_archived:
            return []
        has_invoice = getattr(self, "has_running_invoice", None)
        if has_invoice is None:
            has_invoice = bool(self.running_invoices())
        has_contact = getattr(self, "has_outage_contact", None)
        if has_contact is None:
            has_contact = self.contacts.filter(
                role=SiteContact.OUTAGE, person__is_archived=False
            ).exists()
        keys = []
        if not has_invoice and not self.no_invoice_reason:
            keys.append("no_recurring_invoice")
        if not has_contact:
            keys.append("no_outage_contact")
        return keys

    def problems(self):
        return [str(self.PROBLEMS[key]) for key in self.problem_keys()]


@model_urls
class SiteContact(Model):
    OUTAGE = "outage"
    IT = "it"
    ROLE_CHOICES = [
        (OUTAGE, _("outages and maintenance")),
        (IT, _("IT (DNS etc.)")),
    ]

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, verbose_name=_("site"), related_name="contacts"
    )
    person = models.ForeignKey(
        Person,
        on_delete=models.CASCADE,
        verbose_name=_("person"),
        related_name="site_contacts",
    )
    role = models.CharField(_("role"), max_length=20, choices=ROLE_CHOICES)

    class Meta:
        ordering = ["role", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "person", "role"], name="hosting_sitecontact_unique"
            )
        ]
        verbose_name = _("site contact")
        verbose_name_plural = _("site contacts")

    def __str__(self):
        return f"{self.person} ({self.get_role_display()})"

    def get_absolute_url(self):
        return self.site.get_absolute_url()
