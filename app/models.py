import sqlite3
from datetime import datetime, timezone

from flask import current_app, g


STATUSES = {"pending", "in_transit", "out_for_delivery", "delivered", "cancelled"}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    with app.app_context():
        db = get_db()
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS cargo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT NOT NULL UNIQUE,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL
            )
            """
        )
        db.commit()
        app.teardown_appcontext(close_db)


def cargo_to_dict(cargo):
    return dict(cargo)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")