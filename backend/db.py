"""Small durable SQLite store; replace with migrations/Postgres before scaling."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('submitter','coder','team')), google_sub TEXT,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS otps (
 email TEXT PRIMARY KEY, digest TEXT NOT NULL, expires_at INTEGER NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0, requested_at INTEGER NOT NULL,
 name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('submitter','coder'))
);
CREATE TABLE IF NOT EXISTS sessions (
 digest TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS rate_events (
 kind TEXT NOT NULL, subject TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_subject_time ON rate_events(kind,subject,created_at);
CREATE TABLE IF NOT EXISTS oauth_states (
 digest TEXT PRIMARY KEY, verifier TEXT NOT NULL, nonce TEXT NOT NULL,
 role TEXT NOT NULL, expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS applications (
 id TEXT PRIMARY KEY, user_id TEXT NOT NULL UNIQUE REFERENCES users(id),
 name TEXT NOT NULL, github TEXT NOT NULL, experience TEXT NOT NULL,
 specialty TEXT NOT NULL, portfolio TEXT NOT NULL, bio TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','changes_requested','rejected')),
 notes TEXT NOT NULL DEFAULT '', decided_by TEXT REFERENCES users(id),
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
 id TEXT PRIMARY KEY, owner_id TEXT NOT NULL REFERENCES users(id),
 title TEXT NOT NULL, repo TEXT NOT NULL, sha TEXT NOT NULL,
 stack TEXT NOT NULL, scope TEXT NOT NULL, budget INTEGER NOT NULL,
 deadline TEXT NOT NULL, visibility TEXT NOT NULL,
 category TEXT NOT NULL DEFAULT 'general',
 status TEXT NOT NULL DEFAULT 'Awaiting access',
 platform_access TEXT NOT NULL DEFAULT 'pending',
 reviewer_id TEXT REFERENCES users(id), reviewer_access TEXT NOT NULL DEFAULT 'pending',
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
 id TEXT PRIMARY KEY, review_id TEXT NOT NULL REFERENCES reviews(id),
 user_id TEXT NOT NULL REFERENCES users(id), text TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(id),
 review_id TEXT REFERENCES reviews(id), text TEXT NOT NULL, created_at INTEGER NOT NULL
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self, *, write: bool = False):
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        if write:
            conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            if write:
                conn.commit()
        except BaseException:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self):
        with self.connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
            if "google_sub" not in columns:
                conn.execute("ALTER TABLE users ADD COLUMN google_sub TEXT")
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS unique_google_subject ON users(google_sub) WHERE google_sub IS NOT NULL")
            review_columns = {row[1] for row in conn.execute("PRAGMA table_info(reviews)")}
            if "category" not in review_columns:
                conn.execute("ALTER TABLE reviews ADD COLUMN category TEXT NOT NULL DEFAULT 'general'")
