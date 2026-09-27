"""
Database compatibility layer.

app.py's routes call db.execute(sql, params) using sqlite-style "?"
placeholders and expect dict(row) to work on results — this module keeps
that exact calling convention working against two possible backends:

  * Postgres (production on Vercel) — used whenever DATABASE_URL (or
    POSTGRES_URL, the name Vercel's Postgres/Neon integration injects) is
    set. Serverless functions have a read-only, ephemeral filesystem, so
    SQLite (which needs a writable local file) does not work there.
  * SQLite (local dev) — used when no DATABASE_URL is set, so `python3
    app.py` / start.sh keep working locally with zero setup.
"""
import os
import re

DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
IS_POSTGRES = bool(DATABASE_URL)

_QMARK_RE = re.compile(r'\?')


def _to_pg_placeholders(sql: str) -> str:
    return _QMARK_RE.sub('%s', sql)


if IS_POSTGRES:
    import psycopg2
    import psycopg2.extras

    # Neon/Vercel Postgres requires SSL; add it if the URL doesn't set one.
    _DSN = DATABASE_URL
    if 'sslmode=' not in _DSN:
        _DSN += ('&' if '?' in _DSN else '?') + 'sslmode=require'

    class _PGConn:
        """Wraps a psycopg2 connection so it can be used exactly like the
        sqlite3.Connection object app.py was written against."""

        def __init__(self):
            self._conn = psycopg2.connect(_DSN, cursor_factory=psycopg2.extras.RealDictCursor)

        def execute(self, sql, params=()):
            cur = self._conn.cursor()
            cur.execute(_to_pg_placeholders(sql), tuple(params))
            return cur

        def executescript(self, sql):
            # psycopg2 runs multi-statement, semicolon-separated SQL fine
            # via execute() as long as no parameters are passed.
            cur = self._conn.cursor()
            cur.execute(sql)
            return cur

        def commit(self):
            self._conn.commit()

        def close(self):
            self._conn.close()

    def connect():
        return _PGConn()

else:
    import sqlite3

    DB_PATH = os.path.join(os.path.dirname(__file__), 'travelq.db')

    def connect():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
