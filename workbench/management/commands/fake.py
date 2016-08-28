import faker
import random

from django.core.management import BaseCommand

from accounts.models import User
from contacts.models import Person
from projects.models import Project
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
            Story.objects.create(
                requested_by=owned_by,
                title=f.name(),
                description=f.text(),
                project=project,
                status=random.choice(list(range(10, 70, 10))),
            )
