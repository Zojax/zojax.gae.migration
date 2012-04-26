"""Testing gae.migration."""

import re
import os
import urlparse
import random
import string

from unittest import TestCase

from google.appengine.ext import testbed
from webapp2 import WSGIApplication

from webtest import TestApp

from ndb import model

from .. import migrate

from ..migrate import read_migrations, register_migrations, get_migration_dirs

from ..routes import routes


#from .migrate import DatabaseError

register_migrations("zojax.gae.migration", "migrations")

app = WSGIApplication()

for r in routes:
    app.router.add(r)

def rand_text(size=500):
    words = []
    for i in range(1, 50):
        words.append(''.join([random.choice(string.ascii_letters+'. ') for s in range(1, random.randrange(1,10))]))
    return " ".join(words)

class TestArticle(model.Model):
    title = model.StringProperty()
    description = model.StringProperty()
    created = model.DateTimeProperty(auto_now=True)


class BaseTestCase(TestCase):
    def setUp(self):
        super(BaseTestCase, self).setUp()
        app_id = 'myapp'
        os.environ['APPLICATION_ID'] = app_id
        os.environ['HTTP_HOST'] = app_id

        # First, create an instance of the Testbed class.
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Next, declare which service stubs you want to use.
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.testbed.init_mail_stub()
        self.testbed.init_taskqueue_stub(root_path=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.app = TestApp(app)

    def get_tasks(self):
        return self.testbed.get_stub("taskqueue").GetTasks("default")

    def submit_deferred(self):
        tasks = self.get_tasks()
        taskq = self.testbed.get_stub("taskqueue")
        taskq.FlushQueue("default")
        while tasks:
            for task in tasks:
                params = task["body"].decode('base64')
                self.app.post(task["url"], params)
            tasks = taskq.GetTasks("default")
            taskq.FlushQueue("default")

    def assertContains(self, first, second, msg=None):
        if not second in getattr(first, 'body', first):
            raise self.failureException,\
            (msg or '%r not in %r' % (second, first.body))

        #import nose; nose.tools.set_trace()


class MigrationsTestCase(BaseTestCase):

    def setUp(self):
        super(MigrationsTestCase, self).setUp()
        self.migrations_dict = read_migrations(get_migration_dirs())
        if self.migrations_dict.has_key('zojax.gae.migration'):
            self.migrations = self.migrations_dict['zojax.gae.migration']

        # Initialising 100 TestArticle objects
        for i in range(1, 100):
            article = TestArticle(title= "beautiful article %s" % i, description= rand_text())
            article.put()


    def testReadMigrations(self):
        #test that result is a dict
        self.assertTrue(isinstance(self.migrations_dict, dict))
        # test app registered
        self.assertTrue(self.migrations_dict.has_key('zojax.gae.migration'))
        # we should have 4 test migrations
        self.assertEqual(len(self.migrations_dict['zojax.gae.migration']), 4)

    def testMigrationList(self):
        # currently self.migrations is instance of MigrationList and
        # contains unapplied migrations
        # check that all migrations are not applied
        self.assertEqual(len(self.migrations), len(self.migrations.to_apply()))
        # no migrations can be rolled back
        self.assertTrue(len(self.migrations.to_rollback()) == 0)
        query = self.migrations.url_query_for('apply', self.migrations[0])
        # check that url_query_for provides correct query
        self.assertEqual(set(urlparse.parse_qsl(query)),
                         set([('action', 'apply'),('index', '0'), ('app', 'zojax.gae.migration')])
                        )

    def testApply(self):
        # Check apllying process
        # /_ah/migration/migrate/?action=rollback&index=3&app=inboxer
        target_migration = self.migrations[3]
        res = self.app.get('/_ah/migration/migrate/?%s' % self.migrations.url_query_for('apply', target_migration))
        self.assertEqual(res.status_int, 302)
        self.submit_deferred()
        # test 4 migrations applied successfully
        applied = target_migration.migration_model.query(target_migration.migration_model.status == 'apply success')
        self.assertEqual(applied.count(), 4)

    def testRollback(self):
        self.testApply()
        target_migration = self.migrations[0]
        res = self.app.get('/_ah/migration/migrate/?%s' % self.migrations.url_query_for('rollback', target_migration))

        self.assertEqual(res.status_int, 302)
        self.submit_deferred()
        rollback = target_migration.migration_model.query()
        # should be empty as migration rolled back successfully should be removed
        self.assertEqual(rollback.count(), 0)
        #1/0

    def testTest(self):
        res = self.app.get('/_ah/migration/')
    #        self.assertContains('qweqweqwe','zzz')




#def with_migrations(*migrations):
#    """
#    Decorator taking a list of migrations. Creates a temporary directory writes
#    each migration to a file (named '0.py', '1.py', '2.py' etc), calls the decorated
#    function with the directory name as the first argument, and cleans up the
#    temporary directory on exit.
#    """
#
#    def unindent(s):
#        initial_indent = re.search(r'^([ \t]*)\S', s, re.M).group(1)
#        return re.sub(r'(^|[\r\n]){0}'.format(re.escape(initial_indent)), r'\1', s)
#
#    def decorator(func):
#        tmpdir = mkdtemp()
#        for ix, code in enumerate(migrations):
#            with open(os.path.join(tmpdir, '{0}.py'.format(ix)), 'w') as f:
#                f.write(unindent(code).strip())
#
#        @wraps(func)
#        def decorated(*args, **kwargs):
#            try:
#                func(tmpdir, *args, **kwargs)
#            finally:
#                rmtree(tmpdir)
#
#        return decorated
#    return decorator
#
#@with_migrations(
#    """
#step("CREATE TABLE test (id INT)")
#transaction(
#    step("INSERT INTO test VALUES (1)"),
#    step("INSERT INTO test VALUES ('x', 'y')")
#)
#    """
#)
#def test_transaction_is_not_committed_on_error(tmpdir):
#    conn, paramstyle = connect(dburi)
#    migrations = read_migrations(conn, paramstyle, tmpdir)
#    try:
#        migrations.apply()
#    except DatabaseError:
#        # Expected
#        pass
#    else:
#        raise AssertionError("Expected a DatabaseError")
#    cursor = conn.cursor()
#    cursor.execute("SELECT count(1) FROM test")
#    assert cursor.fetchone() == (0,)
#
#
#@with_migrations(
#    'step("CREATE TABLE test (id INT)")',
#    '''
#step("INSERT INTO test VALUES (1)", "DELETE FROM test WHERE id=1")
#step("UPDATE test SET id=2 WHERE id=1", "UPDATE test SET id=1 WHERE id=2")
#    '''
#)
#def test_rollbacks_happen_in_reverse(tmpdir):
#    conn, paramstyle = connect(dburi)
#    migrations = read_migrations(conn, paramstyle, tmpdir)
#    migrations.apply()
#    cursor = conn.cursor()
#    cursor.execute("SELECT * FROM test")
#    assert cursor.fetchall() == [(2,)]
#    migrations.rollback()
#    cursor.execute("SELECT * FROM test")
#    assert cursor.fetchall() == []
#
#@with_migrations(
#    '''
#    step("CREATE TABLE test (id INT)")
#    step("INSERT INTO test VALUES (1)")
#    step("INSERT INTO test VALUES ('a', 'b')", ignore_errors='all')
#    step("INSERT INTO test VALUES (2)")
#    '''
#)
#def test_execution_continues_with_ignore_errors(tmpdir):
#    conn, paramstyle = connect(dburi)
#    migrations = read_migrations(conn, paramstyle, tmpdir)
#    migrations.apply()
#    cursor = conn.cursor()
#    cursor.execute("SELECT * FROM test")
#    assert cursor.fetchall() == [(1,), (2,)]
#
#@with_migrations(
#    '''
#    step("CREATE TABLE test (id INT)")
#    transaction(
#        step("INSERT INTO test VALUES (1)"),
#        step("INSERT INTO test VALUES ('a', 'b')"),
#        ignore_errors='all'
#    )
#    step("INSERT INTO test VALUES (2)")
#    '''
#)
#def test_execution_continues_with_ignore_errors_in_transaction(tmpdir):
#    conn, paramstyle = connect(dburi)
#    migrations = read_migrations(conn, paramstyle, tmpdir)
#    migrations.apply()
#    cursor = conn.cursor()
#    cursor.execute("SELECT * FROM test")
#    assert cursor.fetchall() == [(2,)]
#
#@with_migrations(
#    '''
#    step("CREATE TABLE test (id INT)")
#    step("INSERT INTO test VALUES (1)", "DELETE FROM test WHERE id=2")
#    step("UPDATE test SET id=2 WHERE id=1", "SELECT nonexistent FROM imaginary", ignore_errors='rollback')
#    '''
#)
#def test_rollbackignores_errors(tmpdir):
#    conn, paramstyle = connect(dburi)
#    migrations = read_migrations(conn, paramstyle, tmpdir)
#    migrations.apply()
#    cursor = conn.cursor()
#    cursor.execute("SELECT * FROM test")
#    assert cursor.fetchall() == [(2,)]
#
#    migrations.rollback()
#    cursor.execute("SELECT * FROM test")
#    assert cursor.fetchall() == []
#
#
#@with_migrations(
#    '''
#    step("CREATE TABLE test (id INT)")
#    step("DROP TABLE test")
#    '''
#)
#def test_specify_migration_table(tmpdir):
#    conn, paramstyle = connect(dburi)
#    migrations = read_migrations(conn, paramstyle, tmpdir, migration_table='another_migration_table')
#    migrations.apply()
#    cursor = conn.cursor()
#    cursor.execute("SELECT id FROM another_migration_table")
#    assert cursor.fetchall() == [(u'0',)]


