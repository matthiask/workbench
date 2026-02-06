#!/bin/sh
set -ex
uv run coverage erase
PYTHONWARNINGS=all uv run coverage run ./manage.py test -v 2 --keepdb $*

if [ $# -eq 0 ]; then
  uv run coverage report
fi
