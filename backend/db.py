# -*- coding: utf-8 -*-
"""SQLite 数据库公共层：连接、建表、读写辅助。

数据库文件：backend/bank.db（可用 init_db.py 重建，已加入 .gitignore 的 *.db）。
"""
import json
import os
import sqlite3
import hashlib
import re
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
    last_selected_at TEXT,                      -- ISO 时间，未抽取过为 NULL
    question_version TEXT NOT NULL DEFAULT '1',
    content_revision TEXT
);

CREATE TABLE IF NOT EXISTS run_records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,                    -- import / validate / stats / publish / draw
    level      INTEGER,
    detail     TEXT,                             -- JSON 摘要
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recording_events (
    recording_id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    speaker_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS coverage_snapshots (
    snapshot_version TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_questions_level ON questions(level);
CREATE INDEX IF NOT EXISTS idx_questions_status ON questions(status);
"""

ALLOWED_STATUS = ["draft", "validated", "rejected", "ready", "published"]


def connect(db_path=None):
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    # 兼容已存在的 bank.db：统一契约字段采用增量迁移，不要求用户删除数据库。
    columns = {r[1] for r in conn.execute("PRAGMA table_info(questions)")}
    if "question_version" not in columns:
        conn.execute("ALTER TABLE questions ADD COLUMN question_version TEXT NOT NULL DEFAULT '1'")
    if "content_revision" not in columns:
        conn.execute("ALTER TABLE questions ADD COLUMN content_revision TEXT")
    conn.commit()


def row_to_item(row) -> dict:
    """把数据库行还原为统一字段的题目对象。"""
    raw_tokens = json.loads(row["tokens"])
    text = row["text"]
    cursor = 0
    tokens = []
    for token in raw_tokens:
        char = token.get("c", "")
        pos = text.find(char, cursor)
        if pos < 0:
            pos = None
        else:
            cursor = pos + len(char)
        display_py = token.get("display_py") or token.get("py", "")
        tokens.append({
            "c": char,
            "py": tone3(display_py),
            "display_py": display_py,
            "display_start": pos,
        })
    revision = row["content_revision"] if "content_revision" in row.keys() else None
    if not revision:
        revision = content_revision(text, tokens)
    version = row["question_version"] if "question_version" in row.keys() else "1"
    return {
        "id": row["id"],
        "question_id": row["id"],
        "question_version": version,
        "content_revision": revision,
        "level": row["level"],
        "text": text,
        "display_text": text,
        "tokens": tokens,
        "grammar": json.loads(row["grammar"]),
        "status": row["status"],
        "rec_count": row["rec_count"],
        "last_selected_at": row["last_selected_at"],
    }


def tone3(value: str) -> str:
    """将常见带调拼音转为总仓库约定的小写数字声调格式。"""
    tone_map = {
        "ā": "a1", "á": "a2", "ǎ": "a3", "à": "a4",
        "ē": "e1", "é": "e2", "ě": "e3", "è": "e4",
        "ī": "i1", "í": "i2", "ǐ": "i3", "ì": "i4",
        "ō": "o1", "ó": "o2", "ǒ": "o3", "ò": "o4",
        "ū": "u1", "ú": "u2", "ǔ": "u3", "ù": "u4",
        "ǖ": "v1", "ǘ": "v2", "ǚ": "v3", "ǜ": "v4",
    }
    out, tone = [], ""
    for ch in (value or "").lower():
        if ch in tone_map:
            base = tone_map[ch]
            out.append(base[0])
            tone = base[1]
        elif ch == "ü":
            out.append("v")
        else:
            out.append(ch)
    normalized = "".join(out)
    if normalized and not normalized[-1].isdigit():
        normalized += tone or "5"
    return normalized


def content_revision(text: str, tokens: list[dict]) -> str:
    payload = text + "\n" + " ".join(f"{t['c']}:{t['py']}" for t in tokens)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def item_to_row(item: dict):
    return (
        item["id"], item["level"], item["text"],
        json.dumps(item["tokens"], ensure_ascii=False),
        json.dumps(item["grammar"], ensure_ascii=False),
        item.get("status", "ready"),
        int(item.get("rec_count", 0)),
        item.get("last_selected_at"),
        item.get("question_version", "1"),
        item.get("content_revision"),
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
