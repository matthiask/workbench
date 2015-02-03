from django.db import models
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


class ProjectManager(models.Model):
    def create_project(self, title):
        project = Project.objects.create(
            title=title,
        )
        project.releases.create(
            title='INBOX',
            is_default=True,
        )
        return project


class Project(models.Model):
    INITIAL = 10
    PROPOSED = 20
    STARTED = 50
    FINISHED = 60
    REJECTED = 100

    STATUS_CHOICES = (
        (INITIAL, _('initial')),
        (PROPOSED, _('proposed')),
        (STARTED, _('started')),
        (FINISHED, _('finished')),
        (REJECTED, _('rejected')),
    )

    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=INITIAL)

    objects = ProjectManager()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('project')
        verbose_name_plural = _('projects')



class Release(models.Model):
    project = models.ForeignKey(
        Project,
        verbose_name=_('project'),
        related_name='releases')

    title = models.CharField(
        _('title'),
        max_length=200)
    is_default = models.BooleanField(
        _('is default'),
        default=False)

    position = models.PositiveIntegerField(
        _('position'),
        default=0)

    class Meta:
        ordering = ('position', 'id')
        verbose_name = _('release')
        verbose_name_plural = _('releases')

    def __str__(self):
        return self.title
