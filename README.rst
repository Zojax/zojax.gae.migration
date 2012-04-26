============
Installation
============

Install the package zojax.gae.migration into your project.

Register your migrations folder of the application next way (typically it is placed in models.py module)::

    from zojax.gae.migration import register_migrations

    register_migrations("your_app_name")

By default migrations folder can be named 'migrations', otherwise you need to specify
a relative path to your migrations::

    register_migrations("your_app_name", "relative/path/to/your/migrations/directory")

Also you need to include zojax.gae.migration's routes in your application like this::

    from zojax.gae.migration import routes as migration_routes

    routes = [
                #Your routes list here
                ...
                PathPrefixRoute('/_ah/migration', migration_routes.routes),
    ]

Usage
-----

For managing migrations visit page `http://your.domain/_ah/migration/ <http://your.domain/_ah/migration/>`_