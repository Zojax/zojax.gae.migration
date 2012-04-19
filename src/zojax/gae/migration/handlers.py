# -*- coding: utf-8 -*-

import os
import webapp2, ndb

from jinja2 import Template
from webapp2_extras import jinja2

from google.appengine.ext import db
from google.appengine.api import taskqueue

from .migrate import default_config, MigrationEntry
from .migrate import read_migrations


class BaseHandler(webapp2.RequestHandler):
    """
         BaseHandler for all requests

         Holds the auth and session properties so they are reachable for all requests
     """
    config_key = __name__

    def __init__(self, request=None, response=None):
        super(BaseHandler, self).__init__(request=request, response=response)

        self.config = request.app.config.load_config(self.config_key,
                        default_values=default_config,
                        #user_values=config
                        )
        self.migration_model = self.config.get("migration_model", MigrationEntry)
        self.migrations_dirs = self.config.get("migrations_dirs", set([]))
        self.migrations = read_migrations(self.migrations_dirs)


    @webapp2.cached_property
    def jinja2(self):
        # Returns a Jinja2 renderer cached in the app registry.
        return jinja2.get_jinja2(app=self.app)

    def render_response(self, _template, **context):
        # Renders a template and writes the result to the response.

        context["request"] = self.request
        context["uri_for"] = self.uri_for

        rv = self.jinja2.render_template(_template, **context)

        self.response.write(rv)



class MigrationHandler(BaseHandler):
    """
    Handler for running the migrations.
    """
    template = Template(open(os.path.join(os.path.dirname(__file__),
                                            "templates",
                                            "migrate.html")).read())
    def get(self):

        #import pdb; pdb.set_trace()

        self.render_response(self.template, **{
                                                "entities": self.migrations,
                                                })

        return


class QueueHandler(BaseHandler):
    """
    Puts migrations into task queue.
    """

    def get(self):

        action = self.request.GET.get("action")
        index = self.request.GET.get("index")

        if action is None or index is None:
            return

        migration = None
        try:
            migration = self.migrations[int(index)]
        except (ValueError, IndexError):
            pass
        if migration is not None and action in ("apply", "rollback", "reapply"):

            taskqueue.add(url=self.uri_for("migration_worker"), #'/worker/',
                          params={'index': index,
                                  'action': action})

        self.redirect_to("migration")

        return


class MigrationWorker(BaseHandler):

    def post(self): # should run at most 1/s
        action = self.request.get('action')
        migration = self.migrations[int(self.request.get('index'))]

        def migrate():
            getattr(migration, action)()

        db.run_in_transaction(migrate)