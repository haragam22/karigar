"""Service-side store (Phase 7): jobs, chat messages, uploaded files, conversations.

Stdlib `sqlite3`, one file `<service dir>/service.sqlite3` (on Render: the instance disk, which is
ephemeral on the free plan: a redeploy or restart forgets jobs and files — decisions.md).
The worker's own `OrderStore` (karigar/core/orders.py) stays the source of truth for orders; this
store holds what the service needs to answer chats: the queue, progress lines, the results the
worker uploaded and the files it uploaded.

Job states: queued → running → solved (spec/weight/quote known, renders running) → done | failed.
`delivered`: 0 nothing sent, 1 numbers sent (renders pending), 2 everything sent.
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    conv_key TEXT,
    agent TEXT,
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created REAL NOT NULL,
    updated REAL NOT NULL,
    lease_until REAL,
    attempts INTEGER NOT NULL DEFAULT 0,
    progress_json TEXT NOT NULL DEFAULT '[]',
    partial_json TEXT,
    result_json TEXT,
    error TEXT,
    order_id TEXT,
    delivered INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS jobs_conv ON jobs(conv_key, created);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, created);
CREATE TABLE IF NOT EXISTS messages (
    idem_key TEXT PRIMARY KEY,
    conv_key TEXT,
    job_id TEXT,
    reply TEXT,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS files (
    token TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    ctype TEXT NOT NULL,
    size INTEGER NOT NULL,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS convs (
    conv_key TEXT PRIMARY KEY,
    first_seen REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
"""

ACTIVE = ("queued", "running", "solved")
MAX_PROGRESS = 40           # lines kept per job
MAX_LINE = 300              # chars per progress line


@dataclass
class Job:
    job_id: str
    conv_key: str | None
    agent: str | None
    kind: str
    payload: dict
    status: str
    created: float
    updated: float
    lease_until: float | None
    attempts: int
    progress: list
    partial: dict | None
    result: dict | None
    error: str | None
    order_id: str | None
    delivered: int

    @property
    def active(self) -> bool:
        return self.status in ACTIVE


def _row_job(r) -> Job:
    return Job(r["job_id"], r["conv_key"], r["agent"], r["kind"], json.loads(r["payload_json"]),
               r["status"], r["created"], r["updated"], r["lease_until"], r["attempts"],
               json.loads(r["progress_json"]),
               json.loads(r["partial_json"]) if r["partial_json"] else None,
               json.loads(r["result_json"]) if r["result_json"] else None,
               r["error"], r["order_id"], r["delivered"])


class JobStore:
    def recent(self, limit: int = 200) -> list[Job]:
        with self._tx() as con:
            rows = con.execute("SELECT * FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [_row_job(r) for r in rows]

    def __init__(self, path: Path | str, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock
        self._lock = threading.Lock()       # one writer at a time inside this process
        con = sqlite3.connect(self.path, timeout=10)
        try:
            con.executescript(SCHEMA)       # executescript commits on its own
        finally:
            con.close()

    def _tx(self):
        store = self

        class _Tx:
            def __enter__(self):
                store._lock.acquire()
                self.con = sqlite3.connect(store.path, timeout=10, isolation_level=None)
                self.con.row_factory = sqlite3.Row
                self.con.execute("BEGIN IMMEDIATE")
                return self.con

            def __exit__(self, et, e, tb):
                try:
                    self.con.execute("COMMIT" if et is None else "ROLLBACK")
                finally:
                    self.con.close()
                    store._lock.release()
                return False
        return _Tx()

    # ------------------------------------------------------------- conversations
    def conv_first_seen(self, key: str) -> float | None:
        with self._tx() as con:
            r = con.execute("SELECT first_seen FROM convs WHERE conv_key = ?", (key,)).fetchone()
        return None if r is None else r[0]

    def conv_touch(self, key: str) -> None:
        with self._tx() as con:
            con.execute("INSERT OR IGNORE INTO convs (conv_key, first_seen) VALUES (?, ?)",
                        (key, self.clock()))

    # ------------------------------------------------------------- messages
    def message(self, idem: str) -> dict | None:
        with self._tx() as con:
            r = con.execute("SELECT * FROM messages WHERE idem_key = ?", (idem,)).fetchone()
        return dict(r) if r else None

    def add_message(self, idem: str, conv_key: str | None, job_id: str | None,
                    reply: str | None = None) -> dict:
        """Record a chat message; if the key exists (a retry raced us) the first record wins."""
        with self._tx() as con:
            con.execute("INSERT OR IGNORE INTO messages (idem_key, conv_key, job_id, reply, created)"
                        " VALUES (?, ?, ?, ?, ?)", (idem, conv_key, job_id, reply, self.clock()))
            return dict(con.execute("SELECT * FROM messages WHERE idem_key = ?", (idem,)).fetchone())

    # ------------------------------------------------------------- jobs
    def enqueue(self, kind: str, payload: dict, conv_key: str | None = None,
                agent: str | None = None, idem: str | None = None) -> tuple[Job, bool]:
        """A new queued job, or (with `idem`) the job already recorded for that key.
        Returns (job, created). Message record and job are written in one transaction, so a
        retried request can never create a second job."""
        now = self.clock()
        with self._tx() as con:
            if idem is not None:
                r = con.execute("SELECT job_id FROM messages WHERE idem_key = ?", (idem,)).fetchone()
                if r is not None and r["job_id"]:
                    j = con.execute("SELECT * FROM jobs WHERE job_id = ?", (r["job_id"],)).fetchone()
                    return _row_job(j), False
            job_id = "J-" + secrets.token_hex(8)
            con.execute("INSERT INTO jobs (job_id, conv_key, agent, kind, payload_json, status,"
                        " created, updated) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)",
                        (job_id, conv_key, agent, kind, json.dumps(payload, ensure_ascii=False), now, now))
            if idem is not None:
                con.execute("INSERT INTO messages (idem_key, conv_key, job_id, created)"
                            " VALUES (?, ?, ?, ?)", (idem, conv_key, job_id, now))
            return _row_job(con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()), True

    def get(self, job_id: str) -> Job | None:
        with self._tx() as con:
            r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        return _row_job(r) if r else None

    def latest_for_conv(self, conv_key: str) -> Job | None:
        with self._tx() as con:
            r = con.execute("SELECT * FROM jobs WHERE conv_key = ? ORDER BY created DESC, rowid DESC"
                            " LIMIT 1", (conv_key,)).fetchone()
        return _row_job(r) if r else None

    def latest_order_for_conv(self, conv_key: str) -> Job | None:
        """The newest job of a conversation whose result names an order."""
        with self._tx() as con:
            r = con.execute("SELECT * FROM jobs WHERE conv_key = ? AND order_id IS NOT NULL"
                            " ORDER BY created DESC, rowid DESC LIMIT 1", (conv_key,)).fetchone()
        return _row_job(r) if r else None

    def jobs_for_order(self, order_id: str) -> list[Job]:
        with self._tx() as con:
            rows = con.execute("SELECT * FROM jobs WHERE order_id = ? ORDER BY created, rowid",
                               (order_id,)).fetchall()
        return [_row_job(r) for r in rows]

    def claim(self, lease_s: float, max_attempts: int = 2) -> Job | None:
        """The oldest queued job (or a running one whose worker vanished before it solved
        anything), marked running with a lease. Also records the worker heartbeat."""
        now = self.clock()
        with self._tx() as con:
            con.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('worker_seen', ?)", (str(now),))
            r = con.execute(
                "SELECT * FROM jobs WHERE status = 'queued' OR (status = 'running' AND"
                " lease_until < ? AND partial_json IS NULL AND attempts < ?)"
                " ORDER BY created, rowid LIMIT 1", (now, max_attempts)).fetchone()
            if r is None:
                return None
            con.execute("UPDATE jobs SET status = 'running', lease_until = ?, attempts = attempts + 1,"
                        " updated = ? WHERE job_id = ?", (now + lease_s, now, r["job_id"]))
            return _row_job(con.execute("SELECT * FROM jobs WHERE job_id = ?", (r["job_id"],)).fetchone())

    def worker_seen(self) -> float | None:
        with self._tx() as con:
            r = con.execute("SELECT v FROM meta WHERE k = 'worker_seen'").fetchone()
        return float(r[0]) if r else None

    def _active(self, con, job_id: str):
        r = con.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
        if r is None:
            raise KeyError(job_id)
        return r

    def progress(self, job_id: str, lines: list[str], lease_s: float) -> None:
        now = self.clock()
        with self._tx() as con:
            r = self._active(con, job_id)
            if r["status"] not in ACTIVE:
                return
            con.execute("INSERT OR REPLACE INTO meta (k, v) VALUES ('worker_seen', ?)", (str(now),))
            prog = json.loads(r["progress_json"])
            prog += [{"t": now, "text": str(x)[:MAX_LINE]} for x in lines if str(x).strip()]
            con.execute("UPDATE jobs SET progress_json = ?, lease_until = ?, updated = ?"
                        " WHERE job_id = ?", (json.dumps(prog[-MAX_PROGRESS:]), now + lease_s, now, job_id))

    def solved(self, job_id: str, partial: dict, lease_s: float) -> None:
        now = self.clock()
        with self._tx() as con:
            r = self._active(con, job_id)
            if r["status"] not in ("running", "queued"):
                return
            con.execute("UPDATE jobs SET status = 'solved', partial_json = ?, order_id = ?,"
                        " lease_until = ?, updated = ? WHERE job_id = ?",
                        (json.dumps(partial, ensure_ascii=False), partial.get("order_id"),
                         now + lease_s, now, job_id))

    def finish(self, job_id: str, result: dict) -> None:
        now = self.clock()
        with self._tx() as con:
            r = self._active(con, job_id)
            if r["status"] in ("done", "failed"):
                return                              # a duplicate upload changes nothing
            oid = result.get("order_id") if result.get("status") in ("done", "infeasible") else None
            con.execute("UPDATE jobs SET status = 'done', result_json = ?, order_id = COALESCE(?, order_id),"
                        " updated = ? WHERE job_id = ?",
                        (json.dumps(result, ensure_ascii=False), oid, now, job_id))

    def fail(self, job_id: str, error: str) -> None:
        now = self.clock()
        with self._tx() as con:
            r = self._active(con, job_id)
            if r["status"] in ("done", "failed"):
                return
            con.execute("UPDATE jobs SET status = 'failed', error = ?, updated = ? WHERE job_id = ?",
                        (str(error)[:300], now, job_id))

    def mark_delivered(self, job_id: str, level: int) -> None:
        with self._tx() as con:
            con.execute("UPDATE jobs SET delivered = MAX(delivered, ?) WHERE job_id = ?", (level, job_id))

    def reap(self, render_timeout_s: float, max_attempts: int = 2) -> list[str]:
        """Jobs whose worker went silent: solved ones end as done with their numbers only
        (`error` = renders_timeout); running ones past their last attempt fail."""
        now = self.clock()
        out = []
        with self._tx() as con:
            for r in con.execute("SELECT * FROM jobs WHERE status IN ('running', 'solved')"
                                 " AND lease_until < ?", (now,)).fetchall():
                if r["status"] == "solved" and r["updated"] + render_timeout_s < now:
                    con.execute("UPDATE jobs SET status = 'done', result_json = partial_json,"
                                " error = 'renders_timeout', updated = ? WHERE job_id = ?", (now, r["job_id"]))
                    out.append(r["job_id"])
                elif r["status"] == "running" and r["attempts"] >= max_attempts:
                    con.execute("UPDATE jobs SET status = 'failed', error = 'worker_lost', updated = ?"
                                " WHERE job_id = ?", (now, r["job_id"]))
                    out.append(r["job_id"])
        return out

    # ------------------------------------------------------------- files
    def add_file(self, job_id: str, name: str, path: Path, ctype: str, size: int) -> str:
        token = secrets.token_urlsafe(24)           # 192 bits: unguessable
        with self._tx() as con:
            self._active(con, job_id)
            con.execute("INSERT INTO files (token, job_id, name, path, ctype, size, created)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (token, job_id, name, str(path), ctype, int(size), self.clock()))
        return token

    def file(self, token: str) -> dict | None:
        with self._tx() as con:
            r = con.execute("SELECT * FROM files WHERE token = ?", (token,)).fetchone()
        return dict(r) if r else None
