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
    NAMESPACE=feinheit
    OAUTH2_CLIENT_ID=...
    OAUTH2_CLIENT_SECRET=...

Prerequisites:

* At least Python 3.8
* Install `fh-fablib <https://github.com/feinheit/fh-fablib/>`__
* Local PostgreSQL and Redis instances

Local setup::

    fl local
    fl pull-db  # Only if you have access to our server, sorry.

Development::

    fl dev

Code style & prettification::

    fl fmt check

Compile the bootstrap library::

    yarn build-bootstrap
