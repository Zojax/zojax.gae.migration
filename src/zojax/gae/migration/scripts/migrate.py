#!/usr/bin/env python
import logging
import optparse
import os
import re
import sys
import termios
import ConfigParser

from ConfigParser import NoSectionError, NoOptionError
from functools import partial
from getpass import getpass

from yoyo.migrate.connections import connect, parse_uri, unparse_uri
from yoyo.migrate.utils import prompt, plural
from yoyo.migrate import Migration, MigrationStep
from yoyo.migrate import DatabaseError
from yoyo.migrate import read_migrations, create_migrations_table
from yoyo.migrate import logger

verbosity_levels = {
    0: logging.ERROR,
    1: logging.WARN,
    2: logging.INFO,
    3: logging.DEBUG
}

def readconfig(path):
    config = ConfigParser.ConfigParser()
    config.read([path])
    return config

def saveconfig(config, path):
    os.umask(077)
    f = open(path, 'w')
    try:
        return config.write(f)
    finally:
        f.close()

class prompted_migration(object):

    def __init__(self, migration, default=None):
        super(prompted_migration, self).__init__()
        self.migration = migration
        self.choice = default

def prompt_migrations(conn, paramstyle, migrations, direction):
    """
    Iterate through the list of migrations and prompt the user to apply/rollback each.
    Return a list of user selected migrations.

    direction
        one of 'apply' or 'rollback'
    """
    migrations = migrations.replace(prompted_migration(m) for m in migrations)

    position = 0
    while position < len(migrations):
        mig = migrations[position]

        choice = mig.choice
        if choice is None:
            if direction == 'apply':
                choice = 'n' if mig.migration.isapplied(conn, paramstyle, migrations.migration_table) else 'y'
            else:
                choice = 'y' if mig.migration.isapplied(conn, paramstyle, migrations.migration_table) else 'n'
        options = ''.join(o.upper() if o == choice else o.lower() for o in 'ynvdaqjk?')

        print ""
        print '[%s]' % (mig.migration.id,)
        response = prompt("Shall I %s this migration?" % (direction,), options)

        if response == '?':
            print ""
            print "y: %s this migration" % (direction,)
            print "n: don't %s it" % (direction,)
            print ""
            print "v: view this migration in full"
            print ""
            print "d: %s the selected migrations, skipping any remaining" % (direction,)
            print "a: %s all the remaining migrations" % (direction,)
            print "q: cancel without making any changes"
            print ""
            print "j: skip to next migration"
            print "k: back up to previous migration"
            print ""
            print "?: show this help"
            continue

        if response in 'yn':
            mig.choice = response
            position += 1
            continue

        if response == 'v':
            print mig.migration.source
            continue

        if response == 'j':
            position = min(len(migrations), position + 1)
            continue

        if response == 'k':
            position = max(0, position - 1)

        if response == 'd':
            break

        if response == 'a':
            for mig in migrations[position:]:
                mig.choice = 'y'
            break

        if response == 'q':
            for mig in migrations:
                mig.choice = 'n'
            break

    return migrations.replace(m.migration for m in migrations if m.choice == 'y')

def make_optparser():

    optparser = optparse.OptionParser(usage="%prog apply|rollback|reapply <migrations> <database>")
    optparser.add_option(
        "-m", "--match", dest="match",
        help="Select migrations matching PATTERN (perl-compatible regular expression)", metavar='PATTERN',
    )
    optparser.add_option(
        "-a", "--all", dest="all", action="store_true",
        help="Select all migrations, regardless of whether they have been previously applied"
    )
    optparser.add_option(
        "-b", "--batch", dest="batch", action="store_true",
        help="Run in batch mode (don't ask before applying/rolling back each migration)"
    )
    optparser.add_option(
        "-v", dest="verbose", action="count",
        help="Verbose output. Use multiple times to increase level of verbosity"
    )
    optparser.add_option(
        "--verbosity", dest="verbosity_level", action="store", type="int",
        help="Set verbosity level (%d-%d)" % (min(verbosity_levels), max(verbosity_levels)),
    )
    optparser.add_option(
        "", "--force", dest="force", action="store_true",
        help="Force apply/rollback of steps even if previous steps have failed"
    )
    optparser.add_option(
        "-p", "--prompt-password", dest="prompt_password", action="store_true",
        help="Prompt for the database password"
    )
    optparser.add_option(
        "", "--no-cache", dest="cache", action="store_false", default=True,
        help="Don't cache database login credentials"
    )
    optparser.add_option(
        "", "--migration-table", dest="migration_table", action="store", default='None',
        help="Name of table to use for storing migration metadata"
    )

    return optparser

def configure_logging(level):
    """
    Configure the python logging module with the requested loglevel
    """
    logging.basicConfig(level=verbosity_levels[level])

def main(argv=None):

    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if opts.verbosity_level:
        verbosity_level = opts.verbosity_level
    else:
        verbosity_level = opts.verbose
    verbosity_level = min(verbosity_level, max(verbosity_levels))
    verbosity_level = max(verbosity_level, min(verbosity_levels))
    configure_logging(verbosity_level)

    command = dburi = migrations_dir = None
    try:
        command, migrations_dir, dburi = args
        migrations_dir = os.path.normpath(os.path.abspath(migrations_dir))
    except ValueError:
        try:
            command, migrations_dir = args
        except ValueError:
            optparser.print_help()
            return
        dburi = None

    config_path = os.path.join(migrations_dir, '.yoyo-migrate')
    config = readconfig(config_path)

    if dburi is None and opts.cache:
        try:
            logger.debug("Looking up connection string for %r", migrations_dir)
            dburi = config.get('DEFAULT', 'dburi')
        except (ValueError, NoSectionError, NoOptionError):
            pass

    if opts.migration_table is None:
        try:
            migration_table = config.get('DEFAULT', 'migration_table')
        except (ValueError, NoSectionError, NoOptionError):
            migration_table = '_yoyo_migration'

    if dburi is None:
        optparser.error(
            "Please specify command, migrations directory and "
            "database connection string arguments"
        )

    if command not in ['apply', 'rollback', 'reapply']:
        optparser.error("Invalid command")

    if opts.prompt_password:
        password = getpass('Password for %s: ' % dburi)
        scheme, username, _, host, port, database = parse_uri(dburi)
        dburi = unparse_uri((scheme, username, password, host, port, database))

    if opts.migration_table:
        migration_table = opts.migration_table
        config.set('DEFAULT', 'migration_table', migration_table)
    # Cache the database this migration set is applied to so that subsequent
    # runs don't need the dburi argument. Don't cache anything in batch mode -
    # we can't prompt to find the user's preference.
    if opts.cache and not opts.batch:
        if not config.has_option('DEFAULT', 'dburi'):
            response = prompt(
                "Save connection string to %s for future migrations?\n"
                "This is saved in plain text and "
                "contains your database password." % (config_path,),
                "yn"
            )
            if response == 'y':
                config.set('DEFAULT', 'dburi', dburi)

        elif config.get('DEFAULT', 'dburi') != dburi:
            response = prompt(
                "Specified connection string differs from that saved in %s. "
                "Update saved connection string?" % (config_path,),
                "yn"
            )
            if response == 'y':
                config.set('DEFAULT', 'dburi', dburi)

        config.set('DEFAULT', 'migration_table', migration_table)
        saveconfig(config, config_path)

    conn, paramstyle = connect(dburi)

    migrations = read_migrations(conn, paramstyle, migrations_dir)

    if opts.match:
        migrations = migrations.filter(lambda m: re.search(opts.match, m.id) is not None)

    if not opts.all:
        if command in ['apply']:
            migrations = migrations.to_apply()

        elif command in ['reapply', 'rollback']:
            migrations = migrations.to_rollback()

    if not opts.batch:
        migrations = prompt_migrations(conn, paramstyle, migrations, command)

    if not opts.batch and migrations:
        if prompt(command.title() + plural(len(migrations), " %d migration", " %d migrations") + " to %s?" % dburi, "Yn") != 'y':
            return 0

    if command == 'reapply':
        migrations.rollback(opts.force)
        migrations.apply(opts.force)

    elif command == 'apply':
        migrations.apply(opts.force)

    elif command == 'rollback':
        migrations.rollback(opts.force)

if __name__ == "__main__":

    main(sys.argv[1:])

