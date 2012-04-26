# -*- coding: utf-8 -*-

import os

import urllib

######################
#PATCH FOR ndb IMPORT#
######################
import sys

try:
    import ndb
except ImportError: # pragma: no cover
    from google.appengine.ext import ndb

# Monkey patch for ndb availability
sys.modules['ndb'] = ndb

######################

import ndb
import logging
from logging import getLogger

logger = getLogger(__name__)

from itertools import count
from datetime import datetime

from ndb import model

from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.api import datastore_errors
from google.appengine.api import taskqueue

from .utils import plural


_MIGRATION_DIRS = set([])

def get_migration_dirs():
    """
    Returns a set of registered migration directories
    """
    global _MIGRATION_DIRS

    return _MIGRATION_DIRS


def call_next(migrations, application, target_index, action, worker_url):
    """
    Calculates index of the next migration and starts it.
        * migrations - MigrationList instance, list of all migrations;
        * target_index - index of the target migration from the migrations list;
        * application - application name used in migrations list;
        * action - apply|rollback;
        * worker_url - url of the migration handler;


    """
    assert isinstance(migrations, dict), "migrations should be a dict"
    assert application, "application should not be empty"
    assert isinstance(target_index, (basestring, int)) or target_index is None, "target_index should be int, str or None"
    assert action in ("apply", "rollback"), "action should be apply or rollback"

    logging.info("call_next: called from %s" % str(sys._getframe(1).f_globals["__file__"]))
    logging.info("call_next: target_index -> %s" % str(target_index))

    target_migrations = target_migration = origin_migrations = None
    if isinstance(target_index, basestring) and len(target_index):
        target_index = int(target_index)

    try:
        origin_migrations = migrations[application]
        target_migration = origin_migrations[target_index]
    except (ValueError, IndexError, KeyError, TypeError):
        pass
    if target_migration is not None and target_index is not None and len(origin_migrations):
        if action == "apply":
            target_migrations = origin_migrations[:target_index+1].to_apply()
        elif action == "rollback":
            target_migrations = origin_migrations[target_index:].to_rollback()

        if target_migrations:
            index = origin_migrations.index(target_migrations[0])
            logging.info("call_next: starting new migration task %s" % target_migrations[0].id)
            #import pdb; pdb.set_trace()

            taskqueue.add(url=worker_url,
                params={'index': index,
                        'action': action,
                        'application': application,
                        'target_index': target_index
                })


class AlreadyRegisteredError(Exception):
    """
    Raised when duplicate application registering attempted.
    """
    pass


def register_migrations(app_name, migrations_path="migrations"):
    """
    Registers migrations directory for given app_name. Usually called

    from models.py module of application.

    Raises AlreadyRegisteredError when already registered application or

    migrations path occurs.

    """

    cur_path = os.path.dirname(sys._getframe(1).f_globals["__file__"])

    global _MIGRATION_DIRS

    abs_path = os.path.normpath(os.path.abspath(
                                    os.path.join(cur_path, migrations_path)
                                ))
    valid_appname = app_name.strip()

    for known_app, known_path in _MIGRATION_DIRS:
        if valid_appname == known_app:
            raise AlreadyRegisteredError("Application '%s' has already been registered" % valid_appname)
        if abs_path == known_path:
            raise AlreadyRegisteredError("Migration directory '%s' has already been registered for '%s' application" % (abs_path, known_app))

    _MIGRATION_DIRS.add((valid_appname, abs_path))



class MigrationEntry(model.Model):
    """
    Represents Migration in storage.
    """
    id = model.StringProperty()
    application = model.StringProperty()
    ctime = model.DateTimeProperty(auto_now_add=True)

    status = model.StringProperty(required=True,
                                  choices=["apply in process",
                                           "rollback in process",
                                           "apply failed",
                                           "rollback failed",
                                           "apply success",
                                           "rollback success",
                                           ])

    @classmethod
    def _pre_delete_hook(cls, key):
        memcache.delete(key.kind())

    def _post_put_hook(self, future):
        memcache.delete(self.key.kind())

default_config = {
    'migration_model':  MigrationEntry,
    #'migrations_dirs': _MIGRATION_DIRS,
    }


class Migration(object):

    key = None

    def __init__(self, id, steps, source, application=None, migration_model=MigrationEntry):
        self.id = id
        self.steps = steps
        self.source = source
        self.application = application
        self.migration_model = migration_model
        self.target_index = None # target migration index



    def get_status(self):
        status = "new"
        if self.key is not None:
            migration_object = self.key.get()
            if migration_object:
                return migration_object.status

        migration_query = self.migration_model.query(self.migration_model.id == self.id,
                                                    self.migration_model.application == self.application,
                                                    )
        if migration_query.count() > 0:
            status = migration_query.get().status

        return status

    def set_status(self, status):
        logger.info("setting the migration status to %s" % status)
        if self.key is not None:
            taskqueue.add(url="/_ah/migration/status/",
                          params={'id': self.key.id(),
                                  'status': status})
        #import pdb; pdb.set_trace()

    status = property(get_status, set_status)

    def fail(self):
        logger.info("failing the migration")
        #import time; time.sleep(0.2)
        if self.status == "apply in process":
            self.status = "apply failed"
        if self.status == "rollback in process":
            self.status = "rollback failed"



    def succeed(self):
        #import time; time.sleep(0.2)
        logger.info("succeding the migration with current status %s " % self.status)
#        import pdb; pdb.set_trace()
        action = None
        if self.status == "apply in process":
            self.status = "apply success"
            action = "apply"
        if self.status == "rollback in process":
            self.status = "rollback success"
            action = "rollback"
        call_next(read_migrations(get_migration_dirs()), self.application, self.target_index, action, '/_ah/migration/worker/')


    def isapplied(self, ready_only=False):
        if self.key is not None:
            if ready_only:
                if self.key.get().status != "apply success":
                    return False
            return True

        query = self.migration_model.query(self.migration_model.id == self.id,
                                           self.migration_model.application == self.application,
                                          )
        if ready_only:
            query = query.filter(self.migration_model.status == "apply success")
        return query.count() > 0


    def apply(self, force=False):
        if self.isapplied():
            return
        logger.info("Applying %s", self.id)
        migration = self.migration_model(id=self.id, application=self.application, status="apply in process")
        #future = migration.put_async()
        self.key = migration.put()#future.get_result()
        Migration._process_steps(self.steps, 'apply', self, force=force)



    def rollback(self, force=False):
        if not self.isapplied(ready_only=True):
            return
        logger.info("Rolling back %s", self.id)
        migration = self.migration_model.query(self.migration_model.id == self.id,
                                               self.migration_model.application == self.application).get()
        if migration is not None:
            migration.status="rollback in process"
            self.key = migration.put()

        Migration._process_steps(reversed(self.steps), 'rollback', self, force=force)

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

    def __init__(self, steps, ignore_errors=None, fake_transaction=False):
        assert ignore_errors in (None, 'all', 'apply', 'rollback')
        self.steps = steps
        self.ignore_errors = ignore_errors
        self.fake_transaction = fake_transaction

    def apply(self, migration, force=False):

        def callback(steps, migration, force):
            for step in steps:
                step.apply(migration, force=force)

        try:
            if self.fake_transaction:
                callback(self.steps, migration, force)
            else:
                ndb.transaction(lambda:callback(self.steps, migration, force), xg=True)
        #except datastore_errors.TransactionFailedError:
        except Exception, err:
            if force or self.ignore_errors in ('apply', 'all'):
                logging.exception("Ignored error in transaction while applying")
                return
            migration.fail()
            raise


    def rollback(self, migration, force=False):
        def callback(steps, migration, force):
            for step in reversed(steps):
                step.rollback(migration, force=force)

        try:
            if self.fake_transaction:
                callback(self.steps, migration, force)
            else:
                ndb.transaction(lambda:callback(self.steps, migration, force), xg=True)
        #except datastore_errors.TransactionFailedError:
        except Exception:
            if force or self.ignore_errors in ('rollback', 'all'):
                logging.exception("Ignored error in transaction while rolling back")
                return
            migration.fail()
            raise



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



def read_migrations(directories=_MIGRATION_DIRS, names=None, migration_model=MigrationEntry):
    """
    Return a ``MigrationList`` containing all migrations from ``directory``.
    If ``names`` is given, this only return migrations with names from the given list (without file extensions).
    """
    migrations_dict = {}
    migrations = MigrationList(migration_model)
    paths = []#set([])
    for app_name, dir in directories:
        migrations_dict[app_name] = MigrationList(migration_model)
        for path in os.listdir(dir):
            if path.endswith('.py'):
                paths.append( (app_name, os.path.join(dir, path)) )
    paths.sort()

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

        def step(apply, rollback=None, ignore_errors=None, fake_transaction=True):
            """
            Wrap the given apply and rollback code in a transaction, and add it

            to the list of steps. Return the transaction-wrapped step.

            If fake_transaction is True, transaction won't actually run step in ndb transaction.

            ignore_errors may be "apply", "rollback" or "all". If not provided all errors will be raised

            """
            t = Transaction([MigrationStep(step_id.next(), apply, rollback)], ignore_errors, fake_transaction=fake_transaction)
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
            migrations_dict[app_name].post_apply.append(migration)
            #migrations.post_apply.append(migration)
        else:
            migrations_dict[app_name].append(migration)

    return migrations_dict


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


    def url_query_for(self, action, migration):
        """
        Returns url query string for provided action and migration.
        Possible actions are:
            - apply;
            - rollback;
        migration - migration from migration list

        """
        return urllib.urlencode((('action', action),
                                 ('index', self.index(migration)),
                                 ('app', getattr(migration, 'application', None))
                                ))

    def to_apply(self):
        """
        Return a list of the subset of migrations not already applied.
        """
        return self.__class__(
            self.migration_model,
            [ m for m in self if not m.isapplied() ],
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
            list(reversed([m for m in self if m.isapplied(ready_only=True)])),
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

#    def apply(self, force=False):
#        if not self:
#            return
#        for m in self + self.post_apply:
#            m.apply(force)

#    def rollback(self, force=False):
#        if not self:
#            return
#        for m in self + self.post_apply:
#            m.rollback(force)

    def __getslice__(self, i, j):
        return self.__class__(
            self.migration_model,
            super(MigrationList, self).__getslice__(i, j),
            self.post_apply
        )
