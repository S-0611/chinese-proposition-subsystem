# -*- coding: utf-8 -*-
"""SQLite 数据库公共层：连接、建表、读写辅助。

数据库文件：backend/bank.db（可用 init_db.py 重建，已加入 .gitignore 的 *.db）。
"""
import json
import os
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BANK_DB", str(BACKEND_DIR / "bank.db")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id               TEXT PRIMARY KEY,
    level            INTEGER NOT NULL,
    text             TEXT NOT NULL,
    tokens           TEXT NOT NULL,              -- JSON: [{"c":"我","py":"wǒ"}, ...]
    grammar          TEXT NOT NULL,              -- JSON: ["G1-04", ...]
    status           TEXT NOT NULL DEFAULT 'ready',
    rec_count        INTEGER NOT NULL DEFAULT 0,
    last_selected_at TEXT                       -- ISO 时间，未抽取过为 NULL
);

CREATE TABLE IF NOT EXISTS run_records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,                    -- import / validate / stats / publish / draw
    level      INTEGER,
    detail     TEXT,                             -- JSON 摘要
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_level ON questions(level);
CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status);
"""

ALLOWED_STATUS = ["draft", "validated", "rejected", "ready", "published"]


def connect(db_path=None):
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def row_to_item(row) -> dict:
    """把数据库行还原为统一字段的题目对象。"""
    return {
        "id": row["id"],
        "level": row["level"],
        "text": row["text"],
        "tokens": json.loads(row["tokens"]),
        "grammar": json.loads(row["grammar"]),
        "status": row["status"],
        "rec_count": row["rec_count"],
        "last_selected_at": row["last_selected_at"],
    }


def item_to_row(item: dict):
    return (
        item["id"], item["level"], item["text"],
        json.dumps(item["tokens"], ensure_ascii=False),
        json.dumps(item["grammar"], ensure_ascii=False),
        item.get("status", "ready"),
        int(item.get("rec_count", 0)),
        item.get("last_selected_at"),
    )


def add_run(conn, kind: str, level=None, detail=None):
    from datetime import datetime, timedelta, timezone
    cn = timezone(timedelta(hours=8))
    conn.execute(
        "INSERT INTO run_records (kind, level, detail, created_at) VALUES (?, ?, ?, ?)",
        (kind, level, json.dumps(detail, ensure_ascii=False) if detail is not None else None,
         datetime.now(cn).isoformat(timespec="seconds")),
    )
    conn.commit()
