# -*- coding: utf-8 -*-

import os
import webapp2, ndb

from webapp2_extras import jinja2


class BaseHandler(webapp2.RequestHandler):
    """
         BaseHandler for all requests

         Holds the auth and session properties so they are reachable for all requests
     """
    @webapp2.cached_property
    def jinja2(self):
        # Returns a Jinja2 renderer cached in the app registry.
        return jinja2.get_jinja2(app=self.app)

    def render_response(self, _template, **context):
        # Renders a template and writes the result to the response.

        directory = os.path.dirname(__file__)
        path = os.path.join(directory, 'templates', _template)

        rv = self.jinja2.render_template(path, **context)

        self.response.write(rv)


class MigrationHandler(BaseHandler):
    """
    Handler for running the migrations.
    """
    def get(self):

        self.render_response("migrate.html", **{})

        return
