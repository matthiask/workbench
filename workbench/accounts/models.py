import datetime as dt
from decimal import ROUND_UP, Decimal
from functools import total_ordering

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.signing import BadSignature, Signer
from django.db import connections, models
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from workbench.accounts.features import FEATURES, UserFeatures
from workbench.tools.formats import Z1
from workbench.tools.models import Model
from workbench.tools.urls import model_urls
from workbench.tools.validation import in_days, monday


signer = Signer(salt="user")


class UserManager(BaseUserManager):
    def create_user(self, email, password):
        """
        Creates and saves a User with the given email, date of birth.
        """
        if not email:
            raise ValueError("Users must have an email address")

        from workbench.awt.models import WorkingTimeModel

        user = self.model(
            email=self.normalize_email(email),
            working_time_model=WorkingTimeModel.objects.first(),
        )
        user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        """
        Creates and saves a superuser with the given email, date of birth.
        """
        from workbench.awt.models import WorkingTimeModel

        user = self.model(
            email=self.normalize_email(email),
            working_time_model=WorkingTimeModel.objects.first(),
        )
        user.set_unusable_password()
        user.is_admin = True
        user.save(using=self._db)
        return user

    def choices(self, *, collapse_inactive, myself=False):
        users = {True: [], False: []}
        for user in self.all():
            users[user.is_active].append((user.id, user.get_full_name()))
        choices = [("", _("All users"))]
        if myself:
            choices.append((-1, _("Show mine only")))
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

    def active(self):
        return self.filter(is_active=True)

    def get_by_signed_email(self, signed_email):
        try:
            return self.get(is_active=True, email=signer.unsign(signed_email))
        except BadSignature:
            raise self.model.DoesNotExist


@model_urls
@total_ordering
class User(Model, AbstractBaseUser):
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["working_time_model"]

    email = models.EmailField(_("email"), max_length=254, unique=True)
    is_active = models.BooleanField(_("is active"), default=True)
    is_admin = models.BooleanField(_("is admin"), default=False)

    _short_name = models.CharField(_("initials"), blank=True, max_length=30)
    _full_name = models.CharField(_("full name"), blank=True, max_length=200)

    enforce_same_week_logging = models.BooleanField(
        _("enforce same week logging"), default=True
    )
    language = models.CharField(
        _("language"), max_length=10, choices=settings.LANGUAGES
    )
    working_time_model = models.ForeignKey(
        "awt.WorkingTimeModel",
        on_delete=models.CASCADE,
        verbose_name=_("working time model"),
    )
    planning_hours_per_day = models.DecimalField(
        _("planning hours per day"),
        default=6,
        max_digits=5,
        decimal_places=2,
        help_text=_("How many hours are available for freely planning projects?"),
    )
    person = models.OneToOneField(
        "contacts.Person",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_("person"),
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

    def __lt__(self, other):
        return (
            self.get_full_name() < other.get_full_name()
            if isinstance(other, User)
            else 1
        )

    def get_absolute_url(self):
        return self.urls["detail"] if self.pk else "/"

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
            "today": per_day.get(dt.date.today(), Decimal("0.0")),
            "week": sum(per_day.values(), Decimal("0.0")),
        }

    @cached_property
    def active_projects(self):
        from workbench.projects.models import Project

        return Project.objects.filter(
            Q(
                closed_on__isnull=True,
                id__in=self.loggedhours.filter(rendered_on__gte=in_days(-7))
                .values("service__project")
                .annotate(Count("id"))
                .filter(id__count__gte=3)
                .values("service__project"),
            )
            | Q(
                id__in=self.loggedhours.filter(rendered_on__gte=dt.date.today()).values(
                    "service__project"
                )
            )
        ).select_related("customer", "contact__organization", "owned_by")

    @cached_property
    def signed_email(self):
        return signer.sign(self.email)

    @cached_property
    def features(self):
        return UserFeatures(email=self.email)

    @cached_property
    def latest_created_at(self):
        with connections["default"].cursor() as cursor:
            cursor.execute(
                """
with sq as (
    -- created_at of logged hours with no linked timestamp
    select max(created_at) as created_at
    from logbook_loggedhours
    where rendered_on=%s and rendered_by_id=%s and id not in (
        select logged_hours_id from timer_timestamp
        where logged_hours_id is not NULL
    )

    union all

    -- the end of the latest break
    select max(ends_at) as created_at
    from logbook_break
    where user_id=%s

    union all

    -- the latest timestamp
    select max(created_at) as created_at
    from timer_timestamp
    where user_id=%s

    union all

    -- the latest START timestamp's creation time + logged hours duration
    select max(ts.created_at + make_interval(secs => 3600 * lh.hours))
    from timer_timestamp ts
    left join logbook_loggedhours lh on ts.logged_hours_id=lh.id
    where ts.user_id=%s and ts.type='start'
)
select max(created_at) from sq
                """,
                [dt.date.today(), self.id, self.id, self.id, self.id],
            )
            return list(cursor)[0][0]

    @cached_property
    def hours_since_latest(self):
        return (
            (
                Decimal(int((timezone.now() - self.latest_created_at).total_seconds()))
                / 3600
            ).quantize(Z1, rounding=ROUND_UP)
            if self.latest_created_at
            else Z1
        )

    def take_a_break_warning(self, *, add=0, day=None, request=None):
        if self.features[FEATURES.SKIP_BREAKS]:
            return None

        day = day or dt.date.today()
        hours = (
            self.loggedhours.filter(rendered_on=day)
            .order_by()
            .aggregate(h=Sum("hours"))["h"]
            or Z1
        )
        break_seconds = sum(
            (
                int(brk.timedelta.total_seconds())
                for brk in self.breaks.filter(starts_at__date=day)
            ),
            Z1,
        )
        msg = _(
            "You should take (and log!) a break of at least %(minutes)s minutes"
            " when working more than %(hours)s hours."
        )

        if hours + add >= 9 and break_seconds < 3600:
            msg = msg % {"minutes": 60, "hours": 9}
        elif hours + add >= 7 and break_seconds < 1800:
            msg = msg % {"minutes": 30, "hours": 7}
        elif hours + add >= 5.5 and break_seconds < 900:
            msg = msg % {"minutes": 15, "hours": 5.5}
        else:
            msg = None

        if msg and request:
            messages.warning(request, msg)
        return msg


@model_urls
class Team(Model):
    name = models.CharField(_("name"), max_length=100)
    members = models.ManyToManyField(
        User, related_name="teams", verbose_name=_("members")
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("team")
        verbose_name_plural = _("teams")

    def __str__(self):
        return self.name
