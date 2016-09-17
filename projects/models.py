import itertools
from markdown2 import markdown
import operator

from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import mark_safe, strip_tags
from django.utils.translation import ugettext_lazy as _, ugettext

from accounts.models import User
from contacts.models import Organization, Person
from tools.models import SearchQuerySet, Model
from tools.urls import model_urls


class ProjectQuerySet(SearchQuerySet):
    pass


class SummationDict(dict):
    def __iadd__(self, other):
        for key, value in other.items():
            self[key] = self[key] + value
        return self

    def __getitem__(self, key):
        if key == 'used_percentage':
            try:
                return 100 * self['hours'] / self['planning']
            except Exception:
                return 0

        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return 0


@model_urls()
class Project(Model):
    ACQUISITION = 10
    WORK_IN_PROGRESS = 20
    FINISHED = 30
    DECLINED = 40

    STATUS_CHOICES = (
        (ACQUISITION, _('Acquisition')),
        (WORK_IN_PROGRESS, _('Work in progress')),
        (FINISHED, _('Finished')),
        (DECLINED, _('Declined')),
    )

    customer = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        verbose_name=_('customer'),
        related_name='+')
    contact = models.ForeignKey(
        Person,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        verbose_name=_('contact'),
        related_name='+')

    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('owned by'),
        related_name='+')

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=ACQUISITION)

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    invoicing = models.BooleanField(
        _('invoicing'),
        default=True,
        help_text=_('This project is eligible for invoicing.'))
    maintenance = models.BooleanField(
        _('maintenance'),
        default=False,
        help_text=_('This project is used for maintenance work.'))

    objects = models.Manager.from_queryset(ProjectQuerySet)()

    class Meta:
        ordering = ('-id',)
        verbose_name = _('project')
        verbose_name_plural = _('projects')

    def __str__(self):
        return self.title

    def css(self):
        return {
            self.ACQUISITION: 'warning',
            self.WORK_IN_PROGRESS: '',
            self.FINISHED: 'success',
        }[self.status]

    @cached_property
    def overview(self):
        # Avoid circular imports
        from stories.models import Story, RequiredService, RenderedService

        required = RequiredService.objects.filter(
            story__project=self,
        ).order_by('service_type').values(
            'story',
        ).annotate(
            offered=Sum('offered_effort'),
            planning=Sum('planning_effort'),
        )

        rendered = RenderedService.objects.filter(
            story__project=self,
        ).order_by('rendered_by').values(
            'story',
        ).annotate(
            hours=Sum('hours'),
        )

        stories = self.stories.all()
        story_dict = {}
        stats = SummationDict()

        for story in stories:
            story_dict[story.id] = story
            story.stats = SummationDict()

        for row in required:
            story = story_dict[row.pop('story')]
            d = SummationDict(**row)
            story.stats += d
            stats += d

        for row in rendered:
            story = story_dict[row.pop('story')]
            d = SummationDict(**row)
            story.stats += d
            stats += d

        stories = {
            k: list(v)
            for k, v in
            itertools.groupby(stories, operator.attrgetter('status'))
        }

        return {
            'stats': stats,
            'stories': [
                (value, title, list(stories.get(value, ())))
                for value, title in Story.STATUS_CHOICES
            ],
        }

    def pretty_status(self):
        parts = [self.get_status_display()]
        if not self.invoicing:
            parts.append(ugettext('no invoicing'))
        if self.maintenance:
            parts.append(ugettext('maintenance'))
        return ', '.join(parts)


@model_urls()
class Task(Model):
    INBOX = 10
    BACKLOG = 20
    IN_PROGRESS = 30
    READY_FOR_TEST = 40
    DONE = 50
    ARCHIVED = 60

    STATUS_CHOICES = (
        (INBOX, _('Inbox')),
        (BACKLOG, _('Backlog')),
        (IN_PROGRESS, _('In progress')),
        (READY_FOR_TEST, _('Ready for test')),
        (DONE, _('Done')),
        (ARCHIVED, _('Archived')),
    )

    TASK = 'task'
    BUG = 'bug'
    ENHANCEMENT = 'enhancement'
    QUESTION = 'question'

    TYPE_CHOICES = (
        (TASK, _('Task')),
        (BUG, _('Bug')),
        (ENHANCEMENT, _('Enhancement')),
        (QUESTION, _('Question')),
    )

    BLOCKER = 50
    HIGH = 40
    NORMAL = 30
    LOW = 20

    PRIORITY_CHOICES = (
        (BLOCKER, _('Blocker')),
        (HIGH, _('High')),
        (NORMAL, _('Normal')),
        (LOW, _('Low')),
    )

    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('created by'),
        related_name='+')

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        verbose_name=_('project'),
        related_name='tasks')
    title = models.CharField(
        _('title'),
        max_length=200)
    description = models.TextField(
        _('description'),
        blank=True)
    type = models.CharField(
        _('type'),
        max_length=20,
        choices=TYPE_CHOICES,
        default=TASK,
    )
    priority = models.PositiveIntegerField(
        _('priority'),
        choices=PRIORITY_CHOICES,
        default=NORMAL,
    )
    owned_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('owned by'),
        related_name='+')

    service = models.ForeignKey(
        'offers.Service',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        verbose_name=_('service'),
        related_name='tasks',
    )

    status = models.PositiveIntegerField(
        _('status'),
        choices=STATUS_CHOICES,
        default=INBOX)
    closed_at = models.DateTimeField(
        _('accepted at'),
        blank=True,
        null=True)

    due_on = models.DateField(
        _('due on'),
        blank=True,
        null=True,
        help_text=_('This field should be left empty most of the time.'))

    # position = models.PositiveIntegerField(_('position'), default=0)

    class Meta:
        ordering = ('-priority', 'pk')
        verbose_name = _('task')
        verbose_name_plural = _('task')

    def __str__(self):
        return self.title


class Attachment(Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name=_('task'),
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    title = models.CharField(
        _('title'),
        max_length=200,
        blank=True,
    )
    file = models.FileField(
        _('file'),
        upload_to='attachments/%Y/%m',
    )

    class Meta:
        ordering = ('created_at',)
        verbose_name = _('attachment')
        verbose_name_plural = _('attachments')

    def __str__(self):
        return self.title or self.file.name


class Comment(Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('task'),
    )
    created_at = models.DateTimeField(
        _('created at'),
        default=timezone.now)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        verbose_name=_('created by'),
        related_name='+')
    notes = models.TextField(
        _('notes'),
    )

    def get_absolute_url(self):
        return self.task.urls['detail']

    @property
    def urls(self):
        return self.task.urls

    def html(self):
        return mark_safe(markdown(strip_tags(self.notes)))

    def __str__(self):
        return self.notes[:30] + '...'
