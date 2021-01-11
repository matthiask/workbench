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

    WORK_CATEGORIES = [
        (
            PAID_WORK,
            _("Paid work"),
            _("Paid work"),
        ),
        (
            KNOWLEDGE_TRANSFER,
            _("Knowledge transfer (debriefings, reading, exchanges)"),
            _("Knowledge transfer"),
        ),
        (
            SOCIAL_CARE,
            _(
                "Social care (personal development, people care,"
                " care for the work environment)"
            ),
            _("Social care"),
        ),
        (
            OUTREACH,
            _("Outreach (corporate communication, acquisition)"),
            _("Outreach"),
        ),
        (
            OTHER,
            _("Other (internal administration and coordination, etc.)"),
            _("Other"),
        ),
    ]

    WORK_CATEGORY_CHOICES = [row[:2] for row in WORK_CATEGORIES]
    WORK_CATEGORY_SHORT = {row[0]: row[2] for row in WORK_CATEGORIES}

    circle = models.ForeignKey(
        Circle, on_delete=models.CASCADE, related_name="roles", verbose_name=_("circle")
    )
    name = models.CharField(_("name"), max_length=100)
    for_circle = models.BooleanField(_("for the circle"), default=False)
    is_removed = models.BooleanField(_("is removed"), default=False)
    work_category = models.CharField(
        _("category"),
        max_length=20,
        choices=WORK_CATEGORY_CHOICES,
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

    def get_short_work_category_display(self):
        return self.WORK_CATEGORY_SHORT.get(self.work_category, self.work_category)
