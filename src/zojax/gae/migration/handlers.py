# -*- coding: utf-8 -*-

import os
import webapp2, ndb

from jinja2 import Template
from webapp2_extras import jinja2

from .migrate import default_config, MigrationEntry


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
        self.migrations_dir = self.config.get("migrations_dir", "migrations")
        # os.path.normpath(os.path.abspath(self.migrations_dir))




    @webapp2.cached_property
    def jinja2(self):
        # Returns a Jinja2 renderer cached in the app registry.
        return jinja2.get_jinja2(app=self.app)

    def render_response(self, _template, **context):
        # Renders a template and writes the result to the response.



        #import pdb; pdb.set_trace()

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

        self.render_response(self.template, **{})

        return
