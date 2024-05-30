#!/bin/sh
set -ex
.venv/bin/coverage erase
.venv/bin/python -Wall .venv/bin/coverage run ./manage.py test -v 2 --keepdb $*

if [ $# -eq 0 ]; then
  .venv/bin/coverage report
fi
