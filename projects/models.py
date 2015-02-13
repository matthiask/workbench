from django.db import models
from django.utils.translation import ugettext_lazy as _

from contacts.models import Organization, Person
from tools.models import SearchManager
from tools.urls import model_urls


class ProjectManager(SearchManager):
    def create_project(self, title):
        project = Project.objects.create(
            title=title,
        )
        project.releases.create(
            title='INBOX',
            is_default=True,
        )
        return project


@model_urls()
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

    customer = models.ForeignKey(
        Organization,
        verbose_name=_('customer'),
        related_name='+',
        on_delete=models.PROTECT)
    contact = models.ForeignKey(
        Person,
        blank=True,
        null=True,
        verbose_name=_('contact'),
        related_name='+',
        on_delete=models.SET_NULL)

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

    def __str__(self):
        return self.title


@model_urls()
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
