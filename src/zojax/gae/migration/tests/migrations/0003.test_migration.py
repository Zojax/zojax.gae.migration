# -*- coding: utf-8 -*-

import time, logging


def step1_apply(migration):
    logging.info("3rd migration, apply step 1: empty logic")


def step1_rollback(migration):
    logging.info("3rd migration, rollback step 1: empty logic")
    migration.succeed()

def step2_apply(migration):
    logging.info("3rd migration, apply step 2: empty logic")
    migration.succeed()

def step2_rollback(migration):
    logging.info("3rd migration, rollback step 2: empty logic")



# 1st step
step(step1_apply, step1_rollback)

# 2nd step
step(step2_apply, step2_rollback)
