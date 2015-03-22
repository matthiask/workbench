#!/bin/sh
coverage erase
python -Wall venv/bin/coverage run --branch --include="*ftool*" --omit="*migrations*,*venv*" ./manage.py test -v 2
coverage html
