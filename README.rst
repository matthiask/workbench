=========
Workbench
=========

.. image:: https://github.com/matthiask/workbench/actions/workflows/python-app.yml/badge.svg
    :target: https://github.com/matthiask/workbench/
    :alt: CI Status

Projects, offers, invoices, the logbook, planning, absences and the annual
working time, deals and controlling reports for an agency.

Prerequisites
=============

* Python 3.15 and `uv <https://docs.astral.sh/uv/>`_
* Node.js for the frontend (built with rspack)
* PostgreSQL, e.g. in a container: ``podman start local_postgres_1``
* fh-fablib for the ``fl`` command, installed with
  ``uv tool install fh-fablib``

Recommended contents of ``.env`` (add some random value for
``SECRET_KEY`` and copy the ``OAUTH2_CLIENT_*`` values from the ``.env``
file on the production server)::

    DATABASE_URL=postgres://localhost:5432/workbench
    SECRET_KEY=...
    SENTRY_DSN=
    ALLOWED_HOSTS=["*"]
    DEBUG=True
    LIVE=False
    NAMESPACE=feinheit
    OAUTH2_CLIENT_ID=...
    OAUTH2_CLIENT_SECRET=...

    # For the GitHub estimates importer:
    GITHUB_API_TOKEN=...
    GITHUB_PROJECT_URLS=["https://github.com/orgs/your-org/projects/1"]

Local setup
===========

::

    fl local              # virtualenv and node_modules
    uv run ./manage.py prepare
    uv run ./manage.py createsuperuser

Development
===========

::

    fl dev                # frontend and backend
    ./runtests.sh         # all tests, or e.g. ./runtests.sh workbench.timer
    fl mm && fl cm        # update and compile the translation catalogs

Then, visit http://127.0.0.1:8000/accounts/login/?force_login=EMAIL in your
browser and replace ``EMAIL`` with the email address you used when creating the
superuser. Note that this only works when you're running with ``DEBUG=True``
**and** ``LIVE=False``, this never works in a production environment. The
production environment (and optionally the local environment also) use Google
OAuth2, you can create the necessary credentials here
https://console.cloud.google.com/welcome

You should probably visit the admin panel now and add a few service types incl.
their hourly rate at http://127.0.0.1:8000/admin/services/servicetype/

The admin panel is configured mostly as a read-only interface to your data,
except for the few modules where the admin panel actually works as a management
interface.

Next, visit the contacts list, add an organization, a person working at that
organization, and then you're ready to start adding projects, services etc.

Conventions for contributors (and coding agents) are in ``AGENTS.md``, how
every report and key figure is computed in ``docs/metrics.md``.

Command line interface
======================

``wb`` in ``cli/`` is a client of the JSON API (``/api/``), see
``cli/README.md``. ``wb login`` gets an API token through the browser.

GitHub integration
==================

Workbench can import time estimates from GitHub Project boards into the effort
hours of services:

1. Add a GitHub API token to ``.env`` with ``GITHUB_API_TOKEN=...`` (the
   token needs the ``repo`` scope to access private repositories)
2. Add the project board URLs to ``.env`` with
   ``GITHUB_PROJECT_URLS=["https://github.com/orgs/your-org/projects/1"]``
3. Include GitHub issue URLs in the descriptions of services (e.g. "See
   https://github.com/owner/repo/issues/123")

The update fetches the cards of the boards and sets the effort hours of every
service whose description contains the card's issue URL. Estimates are read
from number fields of the board whose name contains "hour", "time", "estimate"
or "duration". It isn't part of the fairy tasks, run it daily with a separate
cronjob or manually::

    uv run ./manage.py update_service_estimates

Deployment
==========

I am deploying Workbench as a container, the necessary ``Containerfile`` is a
part of this repository. Instead of using an ``.env`` file you should provide
the configuration through environment variables some other way. Workbench sends
a few mails directly through SMTP, so you should probably add the appropriate
``EMAIL_URL`` configuration. See
https://github.com/matthiask/speckenv/blob/main/test_speckenv_django_email_url.py
for examples.

You should set up a cronjob which runs ``./manage.py fairy_tasks`` daily. This
is a requirement for the recurring invoices functionality and other things.

Each installation's deployed commit is the branch ``latest/<installation>``.

Favicon
=======

The rainbow rocket (``workbench/static/workbench/lib/favicon.png``) has been
designed by Sophie for Workbench. Keep it, even if the interface's colors
change.
