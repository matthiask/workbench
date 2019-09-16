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
        for role in self.select_related("circle"):
            circles[role.circle].append(role)
        return [("", "----------")] + [
            (circle.name, [(role.id, str(role)) for role in roles])
            for circle, roles in sorted(circles.items(), key=lambda row: row[0].name)
        ]


class Role(models.Model):
    circle = models.ForeignKey(
        Circle, on_delete=models.CASCADE, related_name="roles", verbose_name=_("circle")
    )
    name = models.CharField(_("name"), max_length=100)
    for_circle = models.BooleanField(_("for the circle"), default=False)
    is_removed = models.BooleanField(_("is removed"), default=False)

    objects = RoleQuerySet.as_manager()

    class Meta:
        ordering = ["is_removed", "-for_circle", "name"]
        verbose_name = _("role")
        verbose_name_plural = _("roles")

    def __str__(self):
        return " ".join(
            filter(
                None,
                [
                    ("(%s)" % gettext("removed")) if self.is_removed else None,
                    ("%s:" % capfirst(gettext("for the circle")))
                    if self.for_circle
                    else None,
                    self.name,
                ],
            )
        )
