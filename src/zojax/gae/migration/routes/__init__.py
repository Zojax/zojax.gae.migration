# -*- coding: utf-8 -*-

from webapp2 import Route

from ..handlers import MigrationHandler, QueueHandler, MigrationWorker, MigrationStatus


# Use defined routes for including into your app in such way:

#from zojax.gae.migration import routes
# routes.append(PathPrefixRoute('/_ah/migrations/', routes.routes))

routes = [

    Route('/', MigrationHandler, name='migration'),
    Route('/migrate/', QueueHandler, name='migration_queue'),
    Route('/worker/', MigrationWorker, name='migration_worker'),
    Route('/status/', MigrationStatus, name='migration_status'),

    ]