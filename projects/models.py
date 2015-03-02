from django.db import models
from django.utils.translation import ugettext_lazy as _

from accounts.models import User
from contacts.models import Organization, Person
from tools.models import SearchManager, ProtectRelationsModel
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
class Project(ProtectRelationsModel):
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

    def overview(self):
        from collections import defaultdict
        from django.db.models import Sum
        from stories.models import RequiredService, RenderedService

        required = RequiredService.objects.filter(
            story__project=self,
        ).order_by('service_type').values(
            'story',
            'service_type__title',
        ).annotate(
            Sum('estimated_effort'),
            Sum('offered_effort'),
            Sum('planning_effort'),
        )

        rendered = RenderedService.objects.filter(
            story__project=self,
        ).order_by('rendered_by').values(
            'story',
            'rendered_by___full_name'
        ).annotate(
            Sum('hours'),
        )

        required_dict = defaultdict(list)
        overall_effort = [0, 0, 0]

        for row in required:
            required_dict[row['story']].append((
                row['service_type__title'],
                row['estimated_effort__sum'],
                row['offered_effort__sum'],
                row['planning_effort__sum'],
            ))
            overall_effort[0] += row['estimated_effort__sum']
            overall_effort[1] += row['offered_effort__sum']
            overall_effort[2] += row['planning_effort__sum']

        rendered_dict = defaultdict(list)
        overall_hours = 0

        for row in rendered:
            rendered_dict[row['story']].append((
                row['rendered_by___full_name'],
                row['hours__sum'],
            ))
            overall_hours += row['hours__sum']

        stories = self.stories.all()
        for story in stories:
            story.required = required_dict.get(story.id, [])
            story.rendered = rendered_dict.get(story.id, [])

        self.overall_effort = overall_effort
        self.overall_hours = overall_hours

        return stories


@model_urls(lambda object: {'project_id': object.project_id, 'pk': object.pk})
class Release(ProtectRelationsModel):
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


Project.allow_delete_if_only = {Project, Release}
Release.allow_delete_if_only = {Release}
