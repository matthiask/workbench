# Thanks to the authors of django-dotenv and django-getenv for the inspiration!

import ast
import os
import warnings


def read_dotenv(filename='.env'):
    """
    Writes the values in ``.env`` in the same folder as this file into
    ``os.environ`` if the keys do not exist already.

    Example::

        DATABASE_URL=...
        CACHE_URL = '...'
        SECRET_KEY = "...."
    """
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        filename)
    if not os.path.isfile(path):
        warnings.warn('%s not a file, not reading anything' % filename)
        return
    # Not sure whether we should try handling other encodings than ASCII
    # at all...
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = [v.strip('\'" \t') for v in line.split('=', 1)]
            os.environ.setdefault(key, value)


def env(key, default=None, required=False):
    """
    An easier way to read values from the environment. Knows how to convert
    Pythonic values such as ``42``, ``None`` into the correct type.
    """
    try:
        value = os.environ[key]
        return ast.literal_eval(value)
    except (SyntaxError, ValueError):
        return value
    except KeyError:
        if required:
            raise Exception(
                'Required key %s not available in environment'
                % repr(key))
        return default
