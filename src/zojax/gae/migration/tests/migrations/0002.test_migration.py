# -*- coding: utf-8 -*-

import time, logging
import random

from ndb import model

#from inboxer.model import
from zojax.gae.migration.tests import TestArticle

TestArticle.add_property("rating", model.IntegerProperty)


def step1_apply(migration):
    logging.info("2nd migration, apply step 1: adding rating")
    for article in TestArticle.query():
        article.author = ["Me", "Other"][random.randrange(0,2)]
        article.rating = random.randrange(1,10)
        article.put()

    #deferred.defer(cycles_func, 2, 1, 1)



def step1_rollback(migration):
    logging.info("2nd migration, rollback step 1: removing rating")
    for article in TestArticle.query():
        article.author = "Me"
        del article.rating
        article.put()
    migration.succeed()

def step2_apply(migration):
    logging.info("2nd migration, apply step 2: changing rating")
    for article in TestArticle.query(TestArticle.author == "Me"):
        article.rating = 9
        article.put()
    migration.succeed()
    #import nose; nose.tools.set_trace()

#def step2_rollback(migration):
#    logging.info("2nd migration, rollback step 2: changing rating")
#    for article in TestArticle.query():
#        article.author = article.author.lower()
#        article.put()

# 1st step
step(step1_apply, step1_rollback)

# 2nd step
step(step2_apply)#, step2_rollback)