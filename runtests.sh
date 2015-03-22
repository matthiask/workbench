#!/bin/sh
coverage erase
python -Wall venv/bin/coverage run --branch --include="*ftool*" --omit="*migrations*,*test_*,*venv*" ./manage.py test -v 2
coverage html
