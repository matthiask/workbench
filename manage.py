#!/usr/bin/env python
import os
import sys

import speckenv


if __name__ == "__main__":  # pragma: no branch
    BASE_DIR = os.path.dirname(__file__)

    speckenv.read_speckenv(
        filename=os.path.join(BASE_DIR, os.environ.get("DOTENV", ".env"))
    )
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workbench.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
