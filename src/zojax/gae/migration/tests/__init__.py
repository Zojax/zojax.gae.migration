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

    @classmethod
    def add_property(cls, name, property, **kwargs):
        """
        Method for dynamical adding model properties
        """
        setattr(cls, name, property(name, **kwargs))
        cls._fix_up_properties()

    @classmethod
    def del_property(cls, name):
        """
        Method for dynamical adding model properties
        """
        delattr(cls, name)
        cls._fix_up_properties()


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
        for i in range(1, 101):
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

    def testFullApply(self):
        # Check apllying process
        # /_ah/migration/migrate/?action=rollback&index=3&app=inboxer
        target_migration = self.migrations[3]
        res = self.app.get('/_ah/migration/tasks/migrate/?%s' % self.migrations.url_query_for('apply', target_migration))
        self.assertEqual(res.status_int, 302)
        self.submit_deferred()
        # test 4 migrations applied successfully
        applied = target_migration.migration_model.query(target_migration.migration_model.status == 'apply success')
        self.assertEqual(applied.count(), 4)

    def testFullRollback(self):
        self.testApply()
        target_migration = self.migrations[0]
        res = self.app.get('/_ah/migration/tasks/migrate/?%s' % self.migrations.url_query_for('rollback', target_migration))

        self.assertEqual(res.status_int, 302)
        self.submit_deferred()
        rollback = target_migration.migration_model.query()
        # should be empty as migration rolled back successfully should be removed
        self.assertEqual(rollback.count(), 0)
        #1/0

    def testApply(self):
        # Applying 1st migration
        target_migration = self.migrations[0]
        self.app.get('/_ah/migration/tasks/migrate/?%s' % self.migrations.url_query_for('apply', target_migration))
        self.submit_deferred()
        # test results of applied migration
        TestArticle.add_property("author", model.StringProperty)
        articles = TestArticle.query(TestArticle.author=="Me")
        self.assertEqual(articles.count(), 100)
        # Applying 2nd migration
        target_migration = self.migrations[1]
        self.app.get('/_ah/migration/tasks/migrate/?%s' % self.migrations.url_query_for('apply', target_migration))
        self.submit_deferred()
        # test results of applied migration
        TestArticle.add_property("rating", model.IntegerProperty)
        articles = TestArticle.query(TestArticle.author=="Me")
        me_artices = articles.count()
        self.assertLess(me_artices, 100)
        # Test that all article of author 'me' has rating 9
        self.assertEqual(me_artices, articles.filter(TestArticle.rating == 9).count())
        TestArticle.del_property("author")

    def testRollback(self):
        # applying 2 migrations
        target_migration = self.migrations[1]
        self.app.get('/_ah/migration/tasks/migrate/?%s' % self.migrations.url_query_for('apply', target_migration))
        self.submit_deferred()
        # rolling back 2nd migration
        target_migration = self.migrations[1]
        self.app.get('/_ah/migration/tasks/migrate/?%s' % self.migrations.url_query_for('rollback', target_migration))
        self.submit_deferred()
        #TestArticle.add_property("rating", model.IntegerProperty)
        articles = TestArticle.query(TestArticle.rating > 0)
        self.assertEqual(articles.count(), 0)
        # rolling back 1st migration
        target_migration = self.migrations[0]
        self.app.get('/_ah/migration/tasks/migrate/?%s' % self.migrations.url_query_for('rollback', target_migration))
        self.submit_deferred()
        articles = TestArticle.query(TestArticle.author.IN(("Me", "Other")))
        self.assertEqual(articles.count(), 0)
