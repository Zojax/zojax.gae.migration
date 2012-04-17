# -*- coding: utf-8 -*-

from webapp2 import Route

from .handlers import MigrationHandler


# Use defined routes for including into your app in such way:

#from zojax.gae.migration import routes
# routes.append(PathPrefixRoute('/_ah/migrations/', routes.routes))

routes = [

    Route('/', MigrationHandler, name='migration'),

    ]