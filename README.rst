=========
Workbench
=========

.. image:: https://travis-ci.org/matthiask/workbench.svg?branch=main
    :target: https://travis-ci.org/matthiask/workbench

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

Local setup::

    fab setup
    fab pull_db:fh

Development::

    fab dev

Code style & prettification::

    tox
    yarn prettier
    yarn eslint

Compile the bootstrap library::

    yarn build-bootstrap
