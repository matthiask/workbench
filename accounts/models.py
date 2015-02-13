from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils.translation import ugettext_lazy as _


class UserManager(BaseUserManager):
    def create_user(self, email, _short_name, _full_name, date_of_birth,
                    password=None):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(
            email=self.normalize_email(email),
            _short_name=_short_name,
            _full_name=_full_name,
            date_of_birth=date_of_birth,
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, _short_name, _full_name, date_of_birth,
                         password):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            email,
            password=password,
            _short_name=_short_name,
            _full_name=_full_name,
            date_of_birth=date_of_birth,
        )
        user.is_admin = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['_full_name', '_short_name', 'date_of_birth']

    email = models.EmailField(_('email'), max_length=254, unique=True)
    is_active = models.BooleanField(_('is active'), default=True)
    is_admin = models.BooleanField(_('is admin'), default=False)
    date_of_birth = models.DateField(_('date of birth'))

    _short_name = models.CharField(_('short name'), blank=True, max_length=30)
    _full_name = models.CharField(_('full name'), blank=True, max_length=200)

    objects = UserManager()

    class Meta:
        ordering = ('_full_name',)
        verbose_name = _('user')
        verbose_name_plural = _('users')

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
