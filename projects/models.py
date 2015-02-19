from django.db import models
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
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
    IN_PREPARATION = 10
    WORK_IN_PROGRESS = 20
    FINISHED = 30

    STATUS_CHOICES = (
        (IN_PREPARATION, _('In preparation')),
        (WORK_IN_PROGRESS, _('Work in progress')),
        (FINISHED, _('Finished')),
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
    owned_by = models.ForeignKey(
        User,
        verbose_name=_('owned by'),
        related_name='+')

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=IN_PREPARATION)

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
