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


Writting the migration
**********************

Every migration file should be a python module and you need to put into the migrations folder (registered earlier).

The order of the migrations is alphabetical, so the most convenient of file naming is 0001.some_migration.py,
0002.another migration.py etc.

There are two functions in the context of migration: step and transaction.
Here is an example of simplest definition of the migration steps logic::

    def step1_apply(migration):
        try:
            # logic for applying the step
        except Exception:
            migration.fail()


    def step1_rollback(migration):
        # logic for rolling back the step
        migration.succeed() # need to succeed the migration manually

    def step2_apply(migration):
        # logic for applying the step
        migration.succeed() # need to succeed the migration manually

    def step2_rollback(migration):
        # possible use case
        try:
            # logic for rolling back the step
        except Exception:
            migration.fail()


The possible usages of the steps are next (without rollback possibility)::

    step(step1_apply)

    step(step2_apply)

Or (apply and rollback functionality)::

    step(step1_apply, step1_rollback)

    step(step2_apply, step2_rollback)

Or (wrapped in transaction)::

    transaction(

        step(step1_apply, step1_rollback),
        step(step2_apply, step2_rollback)
    )

