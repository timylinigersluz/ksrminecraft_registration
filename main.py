# main.py (Production entrypoint)
from app import create_app

# Gunicorn erwartet oft ein Objekt namens "application"
application = create_app()
