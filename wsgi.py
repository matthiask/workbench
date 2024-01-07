import os
from pathlib import Path

import speckenv
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise


BASE_DIR = Path(__file__).resolve().parent

speckenv.read_speckenv(filename=os.environ.get("DOTENV", ".env"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workbench.settings")
application = get_wsgi_application()
application = WhiteNoise(
    application,
    # Serve all static files as immutable
    immutable_file_test=lambda *a: True,
)
application.add_files(BASE_DIR / "static", "/static/")
