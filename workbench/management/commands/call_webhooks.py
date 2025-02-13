import datetime as dt

from django.core.management import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import now
from django_pglocks import advisory_lock
from requests import api
from requests.models import HTTPError

from workbench.webhooks.models import WebhookForward


LOCK_ID = "forward-webhooks"
MAX_RETRIES = 3


class ForwardingError(Exception):
    pass


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Prune forwarded subscription after seven days.",
        )
        parser.add_argument(
            "--retry",
            action="store_true",
            help="Retry failed subscriptions.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=250,
            help="Max. subscriptions to forward in one session (default: %(default)s).",
        )

    def handle(self, *, retry, prune, limit, **options):
        progress = (lambda *a: None) if options["verbosity"] < 2 else self.stdout.write

        handler = webhook_post
        forward_unforwarded(
            handler=handler, retry=retry, limit=limit, progress=progress
        )

        if prune:
            prune_forwarded(progress=progress)


def webhook_post(obj):
    url = obj.configuration.webhook_url
    try:
        api.post(url, json=obj.forward_data)
    except HTTPError as err:
        raise ForwardingError from err
    obj.forwarded_at = now()
    obj.save()


def forward_one(*, handler, obj, progress):
    try:
        handler(obj)
    except ForwardingError as exc:
        obj.forwarding_last_failed_at = now()
        obj.forwarding_retry_count += 1
        obj.forwarding_error_log = "\n".join((
            obj.forwarding_error_log,
            "---",
            str(now()),
            str(exc),
            "",
        ))
        obj.save(
            update_fields=[
                "forwarding_last_failed_at",
                "forwarding_retry_count",
                "forwarding_error_log",
            ]
        )

        progress(f"Failure to forward {obj}: {exc}")
    else:
        progress(f"Forwarded {obj}.")


def forward_unforwarded(*, handler, limit, retry=False, progress):
    with advisory_lock(LOCK_ID, wait=False) as acquired, transaction.atomic():
        if not acquired:
            progress("Unable to acquire forwarding lock, terminating.")
            return

        queryset = (
            WebhookForward.objects.filter(forwarded_at__isnull=True)
            .order_by("pk")
            .select_for_update(skip_locked=True)
        )
        if not retry:
            queryset = queryset.filter(
                Q(forwarding_retry_count__lt=MAX_RETRIES),
                Q(forwarding_last_failed_at__isnull=True)
                | Q(forwarding_last_failed_at__lt=now() - dt.timedelta(hours=1)),
            )
        for obj in queryset[:limit]:
            forward_one(handler=handler, obj=obj, progress=progress)


def prune_forwarded(*, progress):
    if deleted := WebhookForward.objects.filter(
        forwarded_at__isnull=False,
        forwarded_at__lt=now() - dt.timedelta(days=7),
    ).delete()[0]:
        progress(f"Pruned {deleted} entries.")
    else:
        progress("No entries to prune.")
