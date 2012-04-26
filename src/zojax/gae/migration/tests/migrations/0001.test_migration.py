# -*- coding: utf-8 -*-

import time, logging

#from google.appengine.ext import deferred
#from inboxer.model import
from ndb import model

#from zojax.gae.migration.tests import TestArticle

class TestArticle(model.Model):
    title = model.StringProperty()
    description = model.StringProperty()
    created = model.DateTimeProperty(auto_now=True)
    author = model.StringProperty()


def test_step_apply(migration):
    logging.info("Running apply step 1 of migration!! %s " % str(migration))
    for article in TestArticle.query():
        article.author = "me"
        article.put()
    #import nose; nose.tools.set_trace()
    #deferred.defer(cycles_func, 2, 1, 1)
    #cycles_func(2, 1, 1)


def test_step_rollback(migration):
    logging.info("Running rollback step of migration!! %s " % str(migration))
    for article in TestArticle.query():
        del article.author
        article.put()
    migration.succeed()

def test_step2_apply(migration):
    logging.info("Running apply step 2 of migration!! %s " % str(migration))
    for article in TestArticle.query():
        article.author = article.author.capitalize()
        article.put()
    migration.succeed()
    #import nose; nose.tools.set_trace()

def test_step2_rollback(migration):
    logging.info("Running rollback step 2 of migration!! %s " % str(migration))
    for article in TestArticle.query():
        article.author = article.author.lower()
        article.put()

# 1st step
step(test_step_apply, test_step_rollback)


# 2nd step
step(test_step2_apply, test_step2_rollback)
#transaction(
#    step(),
#    step(),
#)