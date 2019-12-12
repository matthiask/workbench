import os

from django.core.wsgi import get_wsgi_application

import speckenv


speckenv.read_speckenv()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workbench.settings")
application = get_wsgi_application()
