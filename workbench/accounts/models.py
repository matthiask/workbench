from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q, Sum
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from workbench.tools.models import Model
from workbench.tools.validation import monday


class UserManager(BaseUserManager):
    def create_user(self, email, password):
        """
        Creates and saves a User with the given email, date of birth.
        """
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(email=self.normalize_email(email))
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email, date of birth.
        """
        user = self.model(email=self.normalize_email(email))
        user.set_unusable_password()
        user.is_admin = True
        user.save(using=self._db)
        return user

    def choices(self, *, collapse_inactive):
        users = {True: [], False: []}
        for user in self.all():
            users[user.is_active].append((user.id, user.get_full_name()))
        choices = [("", _("All users"))]
        if collapse_inactive:
            choices.append((0, _("Inactive users")))
        choices.append((_("Active"), users[True]))
        if users[False] and not collapse_inactive:
            choices.append((_("Inactive"), users[False]))
        return choices

    def active_choices(self, *, include=None):
        users = {True: [], False: []}
        for user in self.filter(Q(is_active=True) | Q(pk=include)):
            users[user.is_active].append((user.id, user.get_full_name()))
        return users[False] + [(_("Active"), users[True])]


class User(Model, AbstractBaseUser):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    email = models.EmailField(_("email"), max_length=254, unique=True)
    is_active = models.BooleanField(_("is active"), default=True)
    is_admin = models.BooleanField(_("is admin"), default=False)

    _short_name = models.CharField(_("short name"), blank=True, max_length=30)
    _full_name = models.CharField(_("full name"), blank=True, max_length=200)

    enforce_same_week_logging = models.BooleanField(
        _("enforce same week logging"), default=True
    )

    objects = UserManager()

    class Meta:
        ordering = ("_full_name",)
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def get_full_name(self):
        return self._full_name or self.get_short_name()

    def get_short_name(self):
        return self._short_name or self.email

    def __str__(self):
        return self.get_full_name()

    def get_absolute_url(self):
        return "/"

    def has_perm(self, perm, obj=None):
        """Does the user have a specific permission?"""
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        """Does the user have permissions to view the app `app_label`?"""
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        """Is the user a member of staff?"""
        # Simplest possible answer: All admins are staff
        return self.is_admin

    @cached_property
    def hours(self):
        per_day = {
            row["rendered_on"]: row["hours__sum"]
            for row in self.loggedhours.filter(rendered_on__gte=monday())
            .order_by()
            .values("rendered_on")
            .annotate(Sum("hours"))
        }

        return {
            "today": per_day.get(date.today(), Decimal("0.0")),
            "week": sum(per_day.values(), Decimal("0.0")),
        }

    @cached_property
    def recent_hours(self):
        return (
            self.loggedhours.filter(rendered_on=date.today())
            .select_related("service__project__owned_by")
            .order_by("-created_at")[:5]
        )

    @cached_property
    def active_projects(self):
        from workbench.projects.models import Project

        return Project.objects.filter(
            id__in=self.loggedhours.filter(
                rendered_on__gte=date.today() - timedelta(days=7)
            ).values("service__project")
        ).select_related("customer", "contact__organization", "owned_by")

    @cached_property
    def important_activities(self):
        return self.activities.open()

    @cached_property
    def in_preparation(self):
        from workbench.invoices.models import Invoice
        from workbench.offers.models import Offer

        invoices = Invoice.objects.filter(
            owned_by=self, status=Invoice.IN_PREPARATION
        ).select_related("project", "owned_by")
        offers = Offer.objects.filter(
            owned_by=self, status=Offer.IN_PREPARATION
        ).select_related("project", "owned_by")

        return list(offers) + list(invoices)
