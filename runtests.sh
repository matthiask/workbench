#!/bin/sh
set -x
venv/bin/coverage erase
venv/bin/python -Wall venv/bin/coverage run ./manage.py test -v 2 --keepdb $*
venv/bin/coverage report
