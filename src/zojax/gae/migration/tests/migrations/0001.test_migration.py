# -*- coding: utf-8 -*-

import time, logging


#from inboxer.model import

def test_step_apply(migration):

    logging.info("Running apply step of migration!! %s " % migration)
    import time
#    for i in range(1,30):
#        logging.info("1 mig: %sth cycle" % str(i))
#        time.sleep(2)

def test_step_rollback(migration):
    logging.info("Running rollback step of migration!! %s " % migration)

def test_step2_apply(migration):

    logging.info("Running apply step 2 of migration!! %s " % migration)
    migration.succeed()

def test_step2_rollback(migration):
    logging.info("Running rollback step 2 of migration!! %s " % migration)

# 1st step
step(test_step_apply, test_step_rollback)


# 2nd step
step(test_step2_apply, test_step2_rollback)
#transaction(
#    step(),
#    step(),
#)