"""Checked-proxy backend — SQLite storage.

Phase 5 implementation: the checked-proxy set is stored in a per-tenant
``checked.db`` SQLite database instead of a flat ``checked.txt`` file. This
turns membership queries (``filter_unchecked``) from O(n) scans into indexed
lookups and removes the O(n^2) behaviour of the old text format.

The on-disk path is derived from the legacy ``txt_path`` (``checked.txt`` ->
``checked.db``) so the storage layouts and ``TenantStorage`` wiring stay
unchanged. On first creation of the database the legacy ``checked.txt`` (if
present) is imported once, mirroring the runs-backend migration pattern.

WAL journaling is preferred for concurrency; environments where WAL is
unavailable (e.g. some OverlayFS Docker images) fall back to DELETE mode.
"""

import os
import sqlite3
import threading
import time

from proxy_forge.utils import normalize_proxy_list, proxy_key


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS checked_proxies (
  proxy_key   TEXT PRIMARY KEY,
  proxy       TEXT NOT NULL,
  checked_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_checked_at ON checked_proxies(checked_at);
"""


def _derive_db_path(txt_path):
    root, _ext = os.path.splitext(txt_path)
    return root + ".db"


class CheckedBackend:
    def __init__(self, txt_path):
        self._txt_path = txt_path
        self._path = _derive_db_path(txt_path)
        self._local = threading.local()

    def path(self):
        return self._path

    def _conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn

        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        db_existed = os.path.isfile(self._path)

        conn = sqlite3.connect(self._path, isolation_level=None, check_same_thread=False)
        try:
            mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            if not mode or str(mode[0]).lower() != "wal":
                conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.DatabaseError:
            conn.execute("PRAGMA journal_mode=DELETE")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript(SCHEMA_SQL)
        self._local.conn = conn

        if not db_existed:
            self._import_legacy_txt(conn)
        return conn

    def _import_legacy_txt(self, conn):
        if not self._txt_path or not os.path.isfile(self._txt_path):
            return
        with open(self._txt_path, "r", encoding="utf-8") as f:
            proxies = normalize_proxy_list(line.strip() for line in f if line.strip())
        if not proxies:
            return
        now = int(time.time())
        conn.executemany(
            "INSERT OR IGNORE INTO checked_proxies(proxy_key, proxy, checked_at) VALUES (?,?,?)",
            [(proxy_key(p), p, now) for p in proxies],
        )

    def list(self):
        rows = self._conn().execute(
            "SELECT proxy FROM checked_proxies ORDER BY checked_at, rowid"
        ).fetchall()
        return [row[0] for row in rows]

    def write(self, proxies):
        proxies = normalize_proxy_list(proxies)
        now = int(time.time())
        conn = self._conn()
        conn.execute("BEGIN")
        try:
            conn.execute("DELETE FROM checked_proxies")
            if proxies:
                conn.executemany(
                    "INSERT OR REPLACE INTO checked_proxies(proxy_key, proxy, checked_at) VALUES (?,?,?)",
                    [(proxy_key(p), p, now) for p in proxies],
                )
            conn.execute("COMMIT")
        except sqlite3.DatabaseError:
            conn.execute("ROLLBACK")
            raise
        return proxies

    def add(self, proxies):
        rows = [
            (proxy_key(p), p, int(time.time()))
            for p in normalize_proxy_list(proxies)
        ]
        if rows:
            self._conn().executemany(
                "INSERT OR IGNORE INTO checked_proxies(proxy_key, proxy, checked_at) VALUES (?,?,?)",
                rows,
            )
        return self.list()

    def filter_unchecked(self, proxies):
        proxies = list(proxies or [])
        if not proxies:
            return []
        keys = [proxy_key(p) for p in proxies]
        conn = self._conn()
        checked = set()
        for start in range(0, len(keys), 900):
            chunk = keys[start:start + 900]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                f"SELECT proxy_key FROM checked_proxies WHERE proxy_key IN ({placeholders})",
                chunk,
            ).fetchall()
            checked.update(row[0] for row in rows)
        return [p for p, k in zip(proxies, keys) if k not in checked]

    def is_checked(self, key):
        row = self._conn().execute(
            "SELECT 1 FROM checked_proxies WHERE proxy_key = ? LIMIT 1",
            (proxy_key(key),),
        ).fetchone()
        return row is not None

    def count(self):
        row = self._conn().execute("SELECT COUNT(*) FROM checked_proxies").fetchone()
        return int(row[0]) if row else 0

    def prune(self, retention_days, max_rows):
        conn = self._conn()
        if retention_days is not None:
            cutoff = int(time.time()) - int(retention_days) * 86400
            conn.execute("DELETE FROM checked_proxies WHERE checked_at < ?", (cutoff,))
        if max_rows is not None:
            conn.execute(
                """
                DELETE FROM checked_proxies WHERE rowid NOT IN (
                    SELECT rowid FROM checked_proxies ORDER BY checked_at DESC, rowid DESC LIMIT ?
                )
                """,
                (int(max_rows),),
            )

    def close(self):
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
