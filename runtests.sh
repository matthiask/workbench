#!/bin/sh
set -x
venv/bin/coverage erase
venv/bin/python -Wall venv/bin/coverage run --branch --include="*workbench*" --omit="*migrations*,*test_*,*venv*,*factories*" ./manage.py test -v 2 --keepdb $*
venv/bin/coverage html
