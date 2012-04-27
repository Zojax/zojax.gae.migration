# -*- coding: utf-8 -*-

import time, logging

#from google.appengine.ext import deferred

from ndb import model

from zojax.gae.migration.tests import TestArticle



TestArticle.add_property("author", model.StringProperty)

def step1_apply(migration):
    logging.info("1st migration, apply step 1: adding author")
    for article in TestArticle.query():
        article.author = "me"
        article.put()

    #deferred.defer(some_func, 'test', 1)



def step1_rollback(migration):
    logging.info("1st migration, rollback step 1: removing author")
    for article in TestArticle.query():
        del article.author
        article.put()
    migration.succeed()

def step2_apply(migration):
    logging.info("1st migration, apply step 2: changing author")
    for article in TestArticle.query():
        article.author = article.author.capitalize()
        article.put()
    migration.succeed()
    #import nose; nose.tools.set_trace()

def step2_rollback(migration):
    logging.info("1st migration, rollback step 2: changing author")
    for article in TestArticle.query():
        article.author = article.author.lower()
        article.put()

# 1st step
step(step1_apply, step1_rollback)

# 2nd step
step(step2_apply, step2_rollback)
