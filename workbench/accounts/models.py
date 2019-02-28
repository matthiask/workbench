from datetime import date, timedelta
from decimal import Decimal
import hashlib

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Sum
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from workbench.tools.models import Model


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


class User(Model, AbstractBaseUser):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    email = models.EmailField(_("email"), max_length=254, unique=True)
    is_active = models.BooleanField(_("is active"), default=True)
    is_admin = models.BooleanField(_("is admin"), default=False)

    _short_name = models.CharField(_("short name"), blank=True, max_length=30)
    _full_name = models.CharField(_("full name"), blank=True, max_length=200)

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
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        per_day = {
            row["rendered_on"]: row["hours__sum"]
            for row in self.loggedhours.filter(rendered_on__gte=monday)
            .order_by()
            .values("rendered_on")
            .annotate(Sum("hours"))
        }

        return {
            "today": per_day.get(today, Decimal("0.00")),
            "week": sum(per_day.values(), Decimal("0.00")),
        }

    @property
    def avatar(self):
        return "https://www.gravatar.com/avatar/%s" % (
            hashlib.md5(self.email.lower().encode("utf-8")).hexdigest(),
        )

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
        ).select_related("owned_by")
