
_schemes = {}

class BadConnectionURI(Exception):
    """
    An invalid connection URI
    """

def connection_for(scheme):
    """
    Register a connection function with a scheme. Each connection function must
    take standard connection arguments and return a dbapi connection object and
    the module used to connect.
    """
    def decorate(func):
        _schemes[scheme] = func
        return func
    return decorate

@connection_for('mysql')
def connect_mysql(username, password, host, port, database):
    import MySQLdb

    kwargs = {}
    if username is not None:
        kwargs['user'] = username
    if password is not None:
        kwargs['passwd'] = password
    if host is not None:
        kwargs['host'] = host
    if port is not None:
        kwargs['port'] = port
    kwargs['db'] = database

    return MySQLdb.connect(**kwargs), MySQLdb.paramstyle

@connection_for('sqlite')
def connect_sqlite(username, password, host, port, database):
    import sqlite3
    return sqlite3.connect(database), sqlite3.paramstyle

@connection_for('postgres')
@connection_for('postgresql')
@connection_for('psql')
def connect_postgres(username, password, host, port, database):
    import psycopg2

    connargs = []
    if username is not None:
        connargs.append('user=%s' % username)
    if password is not None:
        connargs.append('password=%s' % password)
    if port is not None:
        connargs.append('port=%d' % port)
    if host is not None:
        connargs.append('host=%s' % host)
    connargs.append('dbname=%s' % database)
    return psycopg2.connect(' '.join(connargs)), psycopg2.paramstyle

def connect(uri):
    """
    Connect to the given DB uri (in the format
    ``driver://user:pass@host/database_name``), returning a DB-API connection
    object and the paramstyle used by the DB-API module.
    """

    scheme, username, password, host, port, database = parse_uri(uri)
    try:
        connection_func = _schemes[scheme.lower()]
    except KeyError:
        raise BadConnectionURI('Unrecognised database connection scheme %r' % scheme)
    return connection_func(username, password, host, port, database)


def parse_uri(uri):
    """
    Examples::

        >>> parse_uri('postgres://fred:bassett@dbserver:5432/fredsdatabase')
        ('postgres', 'fred', 'bassett', 'dbserver', 5432, 'fredsdatabase')
        >>> parse_uri('mysql:///jimsdatabase')
        ('mysql', None, None, None, None, 'jimsdatabase')
    """
    scheme = username = password = host = port = database = None

    try:
        scheme, uri = uri.split('://', 1)
    except ValueError:
        raise BadConnectionURI("No scheme specified in connection URI %r" % uri)

    try:
        netloc, uri = uri.split('/', 1)
    except ValueError:
        netloc = ''

    try:
        auth, netloc = netloc.split('@', 1)
    except ValueError:
        auth = ''

    if auth:
        try:
            username, password = auth.split(':', 1)
        except ValueError:
            username = auth

    if netloc:
        try:
            host, port = netloc.split(':')
            try:
                port = int(port)
            except ValueError:
                raise BadConnectionURI('Port %r is not numeric' % port)
        except ValueError:
            host = netloc

    database = uri

    return scheme, username, password, host, port, database

def unparse_uri(uri_tuple):
    """
    Examples::

        >>> unparse_uri(('postgres', 'fred', 'bassett', 'dbserver', 5432, 'fredsdatabase'))
        'postgres://fred:bassett@dbserver:5432/fredsdatabase'

        >>> unparse_uri(('postgres', 'pgsql', None, None, None, 'template1'))
        'postgres://pgsql@/template1'

        >>> unparse_uri(('mysql', 'jim', None, 'localhost', None, 'jimsdatabase'))
        'mysql://jim@localhost/jimsdatabase'
    """

    scheme, username, password, host, port, database = uri_tuple
    uri = scheme + "://"
    if username:
        uri += username
        if password:
            uri += ':' + str(password)
        uri += '@'
    if host:
        uri += host
    if port:
        uri += ':%s' % (port,)
    uri += '/'
    uri += database

    return uri

