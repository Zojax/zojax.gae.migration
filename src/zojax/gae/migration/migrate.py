# -*- coding: utf-8 -*-

import os
import sys
import inspect
import logging
import inspect

from itertools import count
from datetime import datetime
from logging import getLogger

logger = getLogger(__name__)

import ndb
from ndb import model
from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.api import datastore_errors
from google.appengine.api import taskqueue

from .utils import plural


_MIGRATIONS_DIRS = set([])



def register_migrations(app_name, dir):
    """
    Registers migrations directory for given app_name. Usually called

    from models.py module of application.

    """
    cur_path = os.path.dirname(sys._getframe(1).f_globals["__file__"])

    global _MIGRATIONS_DIRS

    _MIGRATIONS_DIRS.add(( app_name,
                            os.path.normpath(os.path.abspath(
                                                os.path.join(cur_path,dir)
                                                            )
                                            )
                        ))



class StorageError(Exception):
    pass


class MigrationEntry(model.Model):
    """
    Represents Migration in storage.
    """
    id = model.StringProperty()
    application = model.StringProperty()
    ctime = model.DateTimeProperty(auto_now_add=True)

    status = model.StringProperty(default="in_process",
                                  choices=["in_process",
                                           "failed",
                                           "success"])

    @classmethod
    def _pre_delete_hook(cls, key):
        memcache.delete(key.kind())

    def _post_put_hook(self, future):
        memcache.delete(self.key.kind())

default_config = {
    'migration_model':  MigrationEntry,
    'migrations_dirs': _MIGRATIONS_DIRS,
    }


class Migration(object):

    key = None

    def __init__(self, id, steps, source, application=None, migration_model=MigrationEntry):
        self.id = id
        self.steps = steps
        self.source = source
        self.application = application
        self.migration_model = migration_model
        #import logging
        #logging.info("STEPS -> %s " % str(self.steps))


    @property
    def status(self):
        status = "new"
        migration_query = self.migration_model.query(self.migration_model.id == self.id,
                                                    self.migration_model.application == self.application,
                                                    )
        if migration_query.count() > 0:
            status = migration_query.get().status

        return status

#    @property
#    def migration_object(self):
#        migration_query = self.migration_model.query(self.migration_model.id == self.id,
#                                                     self.migration_model.application == self.application,
#        )
#
#        return migration_query.get()

    def fail(self):
        logger.info("failing the migration")

        taskqueue.add(url="/_ah/migration/status/",
                        params={'id': self.key.id() if self.key else None,
                                'status': "failed"})


    def succeed(self):
        logger.info("succeding the migration")

        taskqueue.add(url="/_ah/migration/status/",
            params={'id': self.key.id() if self.key else None,
                    'status': "success"})


    def isapplied(self):

        return self.migration_model.query(self.migration_model.id == self.id,
                                          self.migration_model.application == self.application,
                                          #self.migration_model.status == "success"
                                          ).count() > 0


    def apply(self, force=False):
        logger.info("Applying %s", self.id)
        migration = self.migration_model(id=self.id, application=self.application)
        self.key = migration.put()
        Migration._process_steps(self.steps, 'apply', self, force=force)



    def rollback(self, force=False):
        logger.info("Rolling back %s", self.id)
        migration = self.migration_model.query(self.migration_model.id == self.id,
                                               self.migration_model.application == self.application).get()
        if migration is not None:
            self.key = migration.key

        Migration._process_steps(reversed(self.steps), 'rollback', self, force=force)

        #if self.key is not None:
            #import pdb; pdb.set_trace()
            #migration.key.delete()

    def reapply(self, force=False):
        self.rollback(force=force)
        self.apply(force=force)

    @staticmethod
    def _process_steps(steps, direction, migration, force=False):

        reverse = {
            'rollback': 'apply',
            'apply': 'rollback',
            }[direction]

        executed_steps = []
        for step in steps:
            try:
                getattr(step, direction)(migration=migration, force=force)
                executed_steps.append(step)

            except datastore_errors.TransactionFailedError:
                exc_info = sys.exc_info()
                migration.fail()
                try:
                    for step in reversed(executed_steps):
                        getattr(step, reverse)(migration=migration, force=force)
                except datastore_errors.TransactionFailedError:
                    logging.exception('Trasaction error when reversing %s of step', direction)
                raise exc_info[0], exc_info[1], exc_info[2]
            except Exception:
                migration.fail()
                raise

class PostApplyHookMigration(Migration):
    """
    A special migration that is run after successfully applying a set of migrations.
    Unlike a normal migration this will be run every time migrations are applied
    script is called.
    """

    def apply(self, force=False):
        logger.info("Applying %s", self.id)
        self.__class__._process_steps(
            self.steps,
            'apply',
            self,
            force=True
        )

    def rollback(self, force=False):
        logger.info("Rolling back %s", self.id)
        self.__class__._process_steps(
            reversed(self.steps),
            'rollback',
            self,
            force=True
        )

class StepBase(object):


    def apply(self, migration, force=False):
        raise NotImplementedError()

    def rollback(self, migration, force=False):
        raise NotImplementedError()

class Transaction(StepBase):
    """
    A ``Transaction`` object causes all associated steps to be run within a
    single database transaction.
    """

    def __init__(self, steps, ignore_errors=None):
        assert ignore_errors in (None, 'all', 'apply', 'rollback')
        self.steps = steps
        self.ignore_errors = ignore_errors

    def apply(self, migration, force=False):

        def callback(steps, migration, force):
            for step in steps:
                step.apply(migration, force=force)

        try:
            ndb.transaction(lambda:callback(self.steps, migration, force), xg=True)
        except datastore_errors.TransactionFailedError:
            if force or self.ignore_errors in ('apply', 'all'):
                logging.exception("Ignored error in transaction while applying")
                return
            migration.fail()
            raise
        except Exception:
            migration.fail()
            raise


    def rollback(self, migration, force=False):
        def callback(steps, migration, force):
            for step in reversed(steps):
                step.rollback(migration, force=force)

        try:
            ndb.transaction(lambda:callback(self.steps, migration, force), xg=True)
        except datastore_errors.TransactionFailedError:
            if force or self.ignore_errors in ('rollback', 'all'):
                logging.exception("Ignored error in transaction while rolling back")
                return
            migration.fail()
            raise
        except Exception:
            migration.fail()
            raise

    def reapply(self, migration, force=False):
        self.rollback(migration, force=force)
        self.apply(migration, force=force)



class MigrationStep(StepBase):
    """
    Model a single migration.

    Each migration step comprises apply and rollback steps of up and down SQL
    statements.
    """

    transaction = None

    def __init__(self, id, apply, rollback):

        self.id = id
        self._rollback = rollback
        self._apply = apply

    def _execute(self, stmt, out=sys.stdout):
        """
        Execute the given statement. If rows are returned, output these in a
        tabulated format.
        """
        if isinstance(stmt, unicode):
            logger.debug(" - executing %r", stmt.encode('ascii', 'replace'))
        else:
            logger.debug(" - executing %r", stmt)
            #cursor.execute(stmt)
        query = ndb.gql(stmt)
        if query:
            result = query.fetch()

            #for row in result:
            #    for ix, value in enumerate(row):
            #        if len(value) > column_sizes[ix]:
            #            column_sizes[ix] = len(value)
            #format = '|'.join(' %%- %ds ' % size for size in column_sizes)
            #out.write(format % tuple(column_names) + "\n")
            #out.write('+'.join('-' * (size + 2) for size in column_sizes) + "\n")
            #for row in result:
            #    out.write((format % tuple(row)).encode('utf8') + "\n")
            #out.write(plural(len(result), '(%d row)', '(%d rows)') + "\n")
            out.write(str(result))

    def apply(self, migration, force=False):
        """
        Apply the step.

        force
            If true, errors will be logged but not be re-raised
        """
        logger.info(" - applying step %d", self.id)
        if not self._apply:
            return

        if isinstance(self._apply, (str, unicode)):
            self._execute(self._apply)
        else:
            self._apply(migration)


    def rollback(self, migration, force=False):
        """
        Rollback the step.
        """
        logger.info(" - rolling back step %d", self.id)
        if self._rollback is None:
            return

        if isinstance(self._rollback, (str, unicode)):
            self._execute(self._rollback)
        else:
            self._rollback(migration)



def read_migrations(directories, names=None, migration_model=MigrationEntry):
    """
    Return a ``MigrationList`` containing all migrations from ``directory``.
    If ``names`` is given, this only return migrations with names from the given list (without file extensions).
    """

    migrations = MigrationList(migration_model)
    paths = set([])
    for app_name, dir in directories:
        for path in os.listdir(dir):
            if path.endswith('.py'):
                paths.add( (app_name, os.path.join(dir, path)) )


    for app_name, path in paths:

        filename = os.path.splitext(os.path.basename(path))[0]

        if filename.startswith('post-apply'):
            migration_class = PostApplyHookMigration
        else:
            migration_class = Migration

        if migration_class is Migration and names is not None and filename not in names:
            continue

        step_id = count(0)
        transactions = []

        def step(apply, rollback=None, ignore_errors=None):
            """
            Wrap the given apply and rollback code in a transaction, and add it
            to the list of steps. Return the transaction-wrapped step.
            """
            t = Transaction([MigrationStep(step_id.next(), apply, rollback)], ignore_errors)
            transactions.append(t)
            return t

        def transaction(*steps, **kwargs):
            """
            Wrap the given list of steps in a single transaction, removing the
            default transactions around individual steps.
            """
            ignore_errors = kwargs.pop('ignore_errors', None)
            assert kwargs == {}

            transaction = Transaction([], ignore_errors)
            for oldtransaction in steps:
                if oldtransaction.ignore_errors is not None:
                    raise AssertionError("ignore_errors cannot be specified within a transaction")
                try:
                    (step,) = oldtransaction.steps
                except ValueError:
                    raise AssertionError("Transactions cannot be nested")
                transaction.steps.append(step)
                transactions.remove(oldtransaction)
            transactions.append(transaction)
            return transaction

        file = open(path, 'r')
        try:
            source = file.read()
            migration_code = compile(source, file.name, 'exec')
        finally:
            file.close()

        ns = {'step' : step, 'transaction': transaction,
             # 'succeed': succeed, 'fail': fail
             }
        exec migration_code in ns
        migration = migration_class(os.path.basename(filename), transactions,
                                    source, application=app_name,
                                    migration_model=migration_model)

        if migration_class is PostApplyHookMigration:
            migrations.post_apply.append(migration)
        else:
            migrations.append(migration)

    return migrations


class MigrationList(list):
    """
    A list of database migrations.

    Use ``to_apply`` or ``to_rollback`` to retrieve subset lists of migrations
    that can be applied/rolled back.
    """


    def __init__(self, migration_model, items=None, post_apply=None):
        super(MigrationList, self).__init__(items if items else [])
        self.migration_model = migration_model
        self.post_apply = post_apply if post_apply else []
        #initialize_connection(self.conn, migration_table)

    def url_query_for(self, action, migration):
        """
        Returns url query string for provided action and migration.
        Possible actions are:
            - apply;
            - rollback;
            - reapply;
        migration - migration from migration list

        """
        query = "action=%(action)s&index=%(index)s"
        index = self.index(migration)

        return query % locals()


    def to_apply(self):
        """
        Return a list of the subset of migrations not already applied.
        """
        return self.__class__(
            self.migration_model,
            [ m for m in self if not m.isapplied(self.migration_model) ],
            self.post_apply
        )

    def to_rollback(self):
        """
        Return a list of the subset of migrations already applied, which may be
        rolled back.

        The order of migrations will be reversed.
        """
        return self.__class__(
            self.migration_model,
            list(reversed([m for m in self if m.isapplied(self.migration_model)])),
            self.post_apply
        )

    def filter(self, predicate):
        return self.__class__(
            self.migration_model,
            [ m for m in self if predicate(m) ],
            self.post_apply
        )

    def replace(self, newmigrations):
        return self.__class__(self.migration_model, newmigrations, self.post_apply)

    def apply(self, force=False):
        if not self:
            return
        for m in self + self.post_apply:
            m.apply(force)

    def rollback(self, force=False):
        if not self:
            return
        for m in self + self.post_apply:
            m.rollback(force)

    def __getslice__(self, i, j):
        return self.__class__(
            self.migration_model,
            super(MigrationList, self).__getslice__(i, j),
            self.post_apply
        )

#def create_migrations_table(conn, tablename):
#    """
#    Create a database table to track migrations
#    """
#    try:
#        cursor = conn.cursor()
#        try:
#            try:
#                cursor.execute("""
#                    CREATE TABLE %s (id VARCHAR(255) NOT NULL PRIMARY KEY, ctime TIMESTAMP)
#                """ % (tablename,))
#                conn.commit()
#            except DatabaseError:
#                pass
#        finally:
#            cursor.close()
#    finally:
#        conn.rollback()


#def initialize_connection(conn, tablename):
#    """
#    Initialize the DBAPI connection for use.
#
#    - Installs ``yoyo.migrate.DatabaseError`` as a base class for the
#      connection's own DatabaseError
#
#    - Creates the migrations table if not already existing
#
#    """
#    module = inspect.getmodule(type(conn))
#    if DatabaseError not in module.DatabaseError.__bases__:
#        module.DatabaseError.__bases__ += (DatabaseError,)
#    create_migrations_table(conn, tablename)


