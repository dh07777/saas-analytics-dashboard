"""Production entry point: gunicorn wsgi:app  |  waitress-serve --port=5000 wsgi:app"""
from app import create_app

app = create_app()
