# Python package.

from migrate import register_migrations, read_migrations, Migration

from .routes import routes

from webapp2 import WSGIApplication

app = WSGIApplication(routes)
