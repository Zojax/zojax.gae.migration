# -*- coding: utf-8 -*-

import time, logging


#from inboxer.model import

def test_step_apply(migration):
    logging.info(" 2 Running apply step of migration!!")

def test_step_rollback(migration):
    logging.info(" 2 Running rollback step of migration!!")

def test_step2_apply(migration):

    logging.info("Running apply step 2 of migration!! %s " % migration)
    migration.succeed()
    #b = 'aa' / 0

def test_step2_rollback(migration):
    logging.info("Running rollback step 2 of migration!! %s " % migration)
    migration.fail()


# 1st step
step(test_step_apply, test_step_rollback)


# 2nd step
step(test_step2_apply, test_step2_rollback)
