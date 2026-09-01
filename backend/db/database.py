import os
import sqlite3
from pathlib import Path

# Default DB path: sibling to backend/ (i.e. <project_root>/cmmi_test.sqlite).
# Override via CMMI_DB_PATH env var — useful for cloud-portable deployments
# and for running parallel instances (v1 + v2) against separate DBs.
_DB_DEFAULT = str(Path(__file__).parent.parent.parent / "cmmi_test.sqlite")
DB_PATH = Path(os.environ.get("CMMI_DB_PATH", _DB_DEFAULT))


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query_all(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    rows = cur.fetchall()
    conn.close()
    return rows


def query_one(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    row = cur.fetchone()
    conn.close()
    return row


def execute(sql, args=()):
    conn = get_db()
    cur = conn.execute(sql, args)
    conn.commit()
    lastrowid = cur.lastrowid
    conn.close()
    return lastrowid