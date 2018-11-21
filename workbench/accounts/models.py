from collections import defaultdict
from datetime import date, timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models import Q
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
        ordering = ("_full_name", "_short_name", "email")
        verbose_name = _("user")
        verbose_name_plural = _("users")

    def get_full_name(self):
        return self._full_name or self.get_short_name()

    def get_short_name(self):
        return self._short_name or self.email

    def __str__(self):
        return self._short_name or self._full_name or self.email

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

    def future_days(self):
        days = defaultdict(lambda: [[], []])
        today = date.today()
        for day in self.days.model._default_manager.filter(
            Q(day__gte=today),
            Q(handled_by=self)
            | Q(handled_by=None, day__lte=today + timedelta(days=30)),
        ).select_related("app"):
            days[day.app][0 if day.handled_by_id else 1].append(day)

        return sorted(days.items(), key=lambda row: row[0].title)
