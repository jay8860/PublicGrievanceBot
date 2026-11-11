"""Central environment configuration.

Loads a local ``.env`` file (when ``python-dotenv`` is installed) and exposes
``get_env()`` -- a tiny wrapper around ``os.getenv()`` that treats blank /
whitespace-only values as "unset", so an empty placeholder in ``.env`` can
never silently override a code default.

``.env`` is for local development only. On a host like Railway, set the same
variables in the platform's dashboard instead: ``load_dotenv()`` never
overrides variables that already exist in the real environment, so
platform-provided values always win.
"""

import logging
import os

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv is an optional convenience
    load_dotenv = None
    logger.warning(
        "python-dotenv is not installed; a local .env file will be ignored. "
        "Run `pip install -r requirements.txt` or export real environment "
        "variables instead."
    )

if load_dotenv is not None:
    # Searches the current working directory (and its parents) for a .env
    # file. A missing file is not an error -- it simply does nothing.
    load_dotenv()


def get_env(name: str, default=None):
    """Return environment variable ``name``, or ``default`` if missing/blank."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value
