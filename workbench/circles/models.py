from collections import defaultdict

from django.db import models
from django.utils.text import capfirst
from django.utils.translation import gettext, gettext_lazy as _


class Circle(models.Model):
    name = models.CharField(_("name"), max_length=100)

    class Meta:
        ordering = ["name"]
        verbose_name = _("circle")
        verbose_name_plural = _("circles")

    def __str__(self):
        return self.name


class RoleQuerySet(models.QuerySet):
    def choices(self):
        circles = defaultdict(list)
        for role in self.filter(is_removed=False).select_related("circle"):
            circles[role.circle].append(role)
        return [("", "----------")] + [
            (circle.name, [(role.id, str(role)) for role in roles])
            for circle, roles in sorted(circles.items(), key=lambda row: row[0].name)
        ]


class Role(models.Model):
    PAID_WORK = "paid-work"
    KNOWLEDGE_TRANSFER = "knowledge-transfer"
    SOCIAL_CARE = "social-care"
    OUTREACH = "outreach"
    OTHER = "other"

    CATEGORIES = [
        (
            PAID_WORK,
            _("Paid work"),
            "",
        ),
        (
            KNOWLEDGE_TRANSFER,
            _("Knowledge transfer"),
            _("debriefings, reading, exchanges"),
        ),
        (
            SOCIAL_CARE,
            _("Social care"),
            _("personal development, people care, care for the work environment"),
        ),
        (
            OUTREACH,
            _("Outreach"),
            _("corporate communication, acquisition"),
        ),
        (
            OTHER,
            _("Other internal matters"),
            _("administration, bookkeeping, coordination, etc."),
        ),
    ]

    CATEGORY_CHOICES = [row[:2] for row in CATEGORIES]
    CATEGORY_DESCRIPTION = {row[0]: row[2] for row in CATEGORIES}

    circle = models.ForeignKey(
        Circle, on_delete=models.CASCADE, related_name="roles", verbose_name=_("circle")
    )
    name = models.CharField(_("name"), max_length=100)
    for_circle = models.BooleanField(_("for the circle"), default=False)
    is_removed = models.BooleanField(_("is removed"), default=False)
    work_category = models.CharField(
        _("category"),
        max_length=20,
        choices=CATEGORY_CHOICES,
        blank=True,
    )

    objects = RoleQuerySet.as_manager()

    class Meta:
        ordering = ["is_removed", "-for_circle", "name"]
        verbose_name = _("role")
        verbose_name_plural = _("roles")

    def __str__(self):
        prefix = gettext("(removed)") + " " if self.is_removed else ""
        if self.for_circle:
            return "%s%s [%s]" % (
                prefix,
                capfirst(gettext("for the circle")),
                self.circle,
            )
        return "%s%s [%s]" % (prefix, self.name, self.circle)

    @property
    def pretty_name(self):
        return capfirst(gettext("for the circle")) if self.for_circle else self.name

    def get_work_category_description(self):
        return self.CATEGORY_DESCRIPTION.get(self.work_category, self.work_category)
