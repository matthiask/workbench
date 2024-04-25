=========
Workbench
=========

.. image:: https://github.com/matthiask/workbench/actions/workflows/python-app.yml/badge.svg
    :target: https://github.com/matthiask/workbench/
    :alt: CI Status

Recommended contents of ``.env`` (add some random value for
``SECRET_KEY`` and copy the ``OAUTH2_CLIENT_*`` values from the ``.env``
file on the production server)::

    DATABASE_URL=postgres://localhost:5432/workbench
    CACHE_URL=hiredis://localhost:6379/1/?key_prefix=workbench
    SECRET_KEY=...
    SENTRY_DSN=
    ALLOWED_HOSTS=["*"]
    DEBUG=True
    LIVE=False
    NAMESPACE=feinheit
    OAUTH2_CLIENT_ID=...
    OAUTH2_CLIENT_SECRET=...

Prerequisites
=============

* At least Python 3.11
* A local PostgreSQL instance

Local setup
===========

    python3 -m venv venv
    . venv/bin/activate
    pip install -U pip
    pip install -r requirements.txt

    ./manage.py prepare
    ./manage.py createsuperuser

Development
===========

    ./manage.py runserver

Then, visit http://127.0.0.1:8000/accounts/login/?force_login=EMAIL in your
browser and replace ``EMAIL`` with the email address you used when creating the
superuser. Note that this only works when you're running with ``DEBUG=True``
**and** ``LIVE=False``, this never works in a production environment.

You should probably visit the admin panel now and add a few service types incl.
their hourly rate at http://127.0.0.1:8000/admin/services/servicetype/

The admin panel is configured mostly as a read-only interface to your data,
except for the few modules where the admin panel actually works as a management
interface.

Next, visit the contacts list, add an organization, a person working at that
organization, and then you're ready to start adding projects, services etc.

Deployment
==========

I am deploying Workbench as a container, the necessary containerfile is a part
of this repository. Instead of using an ``.env`` file you should provide the
configuration through environment variables some other way. Workbench sends a
few mails directly through SMTP, so you should probably add the appropriate
``EMAIL_URL`` configuration. See
https://github.com/matthiask/speckenv/blob/main/test_speckenv_django_email_url.py
for examples.

You should set up a cronjob which runs ``./manage.py fairy_tasks`` daily. This
is a requirement for the recurring invoices functionality and other things.
