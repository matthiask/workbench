import faker
import random

from django.core.management import BaseCommand

from accounts.models import User
from contacts.models import Person
from projects.models import Project, Task
from stories.models import Story


class Command(BaseCommand):
    def handle(self, **options):
        f = faker.Factory.create('de')

        contact = Person.objects.filter(organization__isnull=False).first()
        owned_by = User.objects.first()

        project = Project.objects.create(
            customer=contact.organization,
            contact=contact,
            title=f.name(),
            description=f.text(),
            owned_by=owned_by,
            status=Project.WORK_IN_PROGRESS,
        )

        for i in range(30):
            task = Task.objects.create(
                project=project,
                created_by=owned_by,
                title=f.name(),
                type=random.choice(('task', 'bug', 'enhancement', 'question')),
                priority=random.choice((20, 30, 40, 50)),
                owned_by=random.choice((owned_by, None)),
            )

            for i in range(random.randint(0, 5)):
                task.comments.create(
                    created_by=owned_by,
                    notes=f.text(),
                )

        for i in range(30):
            Story.objects.create(
                requested_by=owned_by,
                title=f.name(),
                description=f.text(),
                project=project,
                status=random.choice(list(range(10, 70, 10))),
            )
