#!/bin/sh
venv/bin/coverage erase
venv/bin/python -Wall venv/bin/coverage run --branch --include="*ftool*" --omit="*migrations*,*test_*,*venv*" ./manage.py test -v 2
venv/bin/coverage html
