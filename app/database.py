"""SQLite хранится вне static; запросы используют параметры, а не конкатенацию."""

import sqlite3
from contextlib import contextmanager


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        yield db
    finally:
        db.close()


def initialize(path):
    # Каталог создаётся при запуске, пустая БД не включается в поставку.
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL,
            service TEXT NOT NULL, message TEXT NOT NULL,
            consent INTEGER NOT NULL, created_at INTEGER NOT NULL,
            fingerprint TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS inquiry_fingerprint ON inquiries(fingerprint, created_at);
        CREATE TABLE IF NOT EXISTS attempts (client TEXT NOT NULL, created_at INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS attempts_client ON attempts(client, created_at);
        """)


def save_inquiry(path, data, fingerprint, client, now, limit, window):
    # Одна транзакция защищает лимит и дедупликацию при одновременных запросах.
    with connect(path) as db:
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute("DELETE FROM attempts WHERE created_at < ?", (now - window,))
            duplicate = db.execute(
                "SELECT id FROM inquiries WHERE fingerprint=? AND created_at>=?",
                (fingerprint, now - 86400),
            ).fetchone()
            if duplicate:
                db.commit()
                return "duplicate"
            count = db.execute(
                "SELECT count(*) FROM attempts WHERE client=?", (client,)
            ).fetchone()[0]
            if count >= limit:
                db.rollback()
                return "limited"
            db.execute("INSERT INTO attempts VALUES (?, ?)", (client, now))
            db.execute(
                "INSERT INTO inquiries(name,email,service,message,consent,created_at,fingerprint) VALUES(?,?,?,?,?,?,?)",
                (
                    data.name,
                    str(data.email),
                    data.service,
                    data.message,
                    1,
                    now,
                    fingerprint,
                ),
            )
            db.commit()
            return "created"
        except Exception:
            db.rollback()
            raise
