"""Gunicorn entry point. `gunicorn wsgi:app`."""
from nobble.app import create_app

app = create_app()
