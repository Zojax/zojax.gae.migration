# -*- coding: utf-8 -*-

from webapp2 import Route

from webapp2_extras.routes import PathPrefixRoute


from ..handlers import MigrationHandler, QueueHandler, MigrationWorker, MigrationStatus


routes = [

    Route('/', MigrationHandler, name='migration'),
    Route('/tasks/migrate/', QueueHandler, name='migration_queue'),
    Route('/tasks/worker/', MigrationWorker, name='migration_worker'),
    Route('/tasks/status/', MigrationStatus, name='migration_status'),

    ]

main_route = PathPrefixRoute('/_ah/migration', routes)
