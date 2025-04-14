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

    # For the GitHub estimates importer:
    GITHUB_API_TOKEN=...
    GITHUB_PROJECT_URLS=["https://github.com/orgs/your-org/projects/1"]

Prerequisites
=============

* At least Python 3.11
* A local PostgreSQL instance

GitHub Integration
==================

Workbench can automatically import time estimates from GitHub Project boards into service effort hours.
To use this feature:

1. Add a GitHub API token in your .env file with ``GITHUB_API_TOKEN=your_token_here`` (the token must have 'repo' scope to access private repositories)
2. Add GitHub project board URLs in your .env file with ``GITHUB_PROJECT_URLS=["https://github.com/orgs/your-org/projects/1"]``
3. Include GitHub issue URLs in your service descriptions (e.g., "See https://github.com/owner/repo/issues/123")
4. The system will automatically update effort hours daily based on time estimates found in the GitHub project board

The integration works as follows:

1. It fetches all cards from the specified GitHub project boards
2. For each card that contains an issue reference and hour estimate, it searches for matching services
3. When a service description contains the corresponding issue URL, it updates the service's effort_hours

The integration looks for time estimates in GitHub Project custom fields (primary method)

- Searches for number fields with names containing 'hour', 'time', 'estimate', or 'duration'
- Works with both classic GitHub Projects and the new GitHub Projects (beta)

You can run the update manually with the command:

.. code-block:: bash

    python manage.py update_service_estimates

Local setup
===========

::

    python3 -m venv venv
    . venv/bin/activate
    pip install -U pip
    pip install -r requirements.txt

    ./manage.py prepare
    ./manage.py createsuperuser

Development
===========

::

    ./manage.py runserver

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
