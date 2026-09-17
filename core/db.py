"""SQLite 연결 · 스키마 · CRUD."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "quantshelf.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    author      TEXT DEFAULT '',
    year        INTEGER,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_books_title ON books(title);

CREATE TABLE IF NOT EXISTS tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    tag_group   TEXT DEFAULT '',
    aliases     TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sentences (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    text            TEXT NOT NULL,
    book_id         INTEGER REFERENCES books(id),
    author          TEXT DEFAULT '',
    page            TEXT DEFAULT '',
    chapter         TEXT DEFAULT '',
    sentence_type   TEXT DEFAULT '미분류',
    score           INTEGER DEFAULT 3,
    note            TEXT DEFAULT '',
    language        TEXT DEFAULT '',
    status          TEXT DEFAULT 'New',
    ease            REAL DEFAULT 2.5,
    interval_days   INTEGER DEFAULT 0,
    repetitions     INTEGER DEFAULT 0,
    due_date        TEXT,
    lapses          INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at      TEXT
);

CREATE TABLE IF NOT EXISTS sentence_tags (
    sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (sentence_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_sentences_book   ON sentences(book_id);
CREATE INDEX IF NOT EXISTS idx_sentences_due    ON sentences(due_date);
CREATE INDEX IF NOT EXISTS idx_sentences_status ON sentences(status);
CREATE INDEX IF NOT EXISTS idx_st_tag           ON sentence_tags(tag_id);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# --------------------------------------------------------------------------- books


def get_or_create_book(title: str, author: str = "", year: Optional[int] = None) -> int:
    title = (title or "").strip()
    if not title:
        raise ValueError("book title is required")
    author = (author or "").strip()
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM books WHERE title = ?", (title,)).fetchone()
        if row:
            # 저자 정보가 비어있던 경우 보강
            if author:
                conn.execute(
                    "UPDATE books SET author = ? WHERE id = ? AND (author IS NULL OR author = '')",
                    (author, row["id"]),
                )
            return row["id"]
        cur = conn.execute(
            "INSERT INTO books (title, author, year) VALUES (?, ?, ?)",
            (title, author, year),
        )
        return cur.lastrowid


def list_books() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT b.id, b.title, b.author, b.year,
                   COUNT(s.id) AS sentence_count
            FROM books b
            LEFT JOIN sentences s
              ON s.book_id = b.id AND s.deleted_at IS NULL
            GROUP BY b.id
            ORDER BY sentence_count DESC, b.title COLLATE NOCASE
            """).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------------------------------------------- tags


def get_or_create_tag(name: str, tag_group: str = "", aliases: str = "") -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("tag name is required")
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        if row:
            return row["id"]
        cur = conn.execute(
            "INSERT INTO tags (name, tag_group, aliases) VALUES (?, ?, ?)",
            (name, tag_group or "", aliases or ""),
        )
        return cur.lastrowid


def list_tags() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT t.id, t.name, t.tag_group,
                   COUNT(s.id) AS sentence_count
            FROM tags t
            LEFT JOIN sentence_tags st ON st.tag_id = t.id
            LEFT JOIN sentences s
              ON s.id = st.sentence_id AND s.deleted_at IS NULL
            GROUP BY t.id
            ORDER BY sentence_count DESC, t.name COLLATE NOCASE
            """).fetchall()
        return [dict(r) for r in rows]


# --------------------------------------------------------------------------- sentences


def insert_sentence(
    *,
    text: str,
    book_id: Optional[int],
    author: str = "",
    page: str = "",
    chapter: str = "",
    sentence_type: str = "미분류",
    score: int = 3,
    note: str = "",
    language: str = "",
    tag_ids: Iterable[int] = (),
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO sentences
                (text, book_id, author, page, chapter,
                 sentence_type, score, note, language, due_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, date('now', '+1 day'))
            """,
            (
                text,
                book_id,
                author,
                page,
                chapter,
                sentence_type,
                score,
                note,
                language,
            ),
        )
        sid = cur.lastrowid
        for tid in tag_ids:
            conn.execute(
                "INSERT OR IGNORE INTO sentence_tags (sentence_id, tag_id) VALUES (?, ?)",
                (sid, tid),
            )
        return sid


def get_sentence(sid: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM sentences WHERE id = ? AND deleted_at IS NULL", (sid,)
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = [
            dict(r)
            for r in conn.execute(
                """
                SELECT t.id, t.name, t.tag_group
                FROM tags t
                JOIN sentence_tags st ON st.tag_id = t.id
                WHERE st.sentence_id = ?
                ORDER BY t.name
                """,
                (sid,),
            ).fetchall()
        ]
        if d.get("book_id"):
            b = conn.execute(
                "SELECT title, author FROM books WHERE id = ?", (d["book_id"],)
            ).fetchone()
            d["book_title"] = b["title"] if b else ""
            d["book_author"] = b["author"] if b else ""
        else:
            d["book_title"] = ""
            d["book_author"] = ""
        return d


def delete_sentence(sid: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE sentences SET deleted_at = datetime('now'), updated_at = datetime('now') "
            "WHERE id = ?",
            (sid,),
        )


def update_sentence(sid: int, **fields) -> None:
    allowed = {
        "text",
        "book_id",
        "author",
        "page",
        "chapter",
        "sentence_type",
        "score",
        "note",
        "language",
    }
    sets = {k: v for k, v in fields.items() if k in allowed}
    if not sets:
        return
    cols = ", ".join(f"{k} = ?" for k in sets)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE sentences SET {cols}, updated_at = datetime('now') WHERE id = ?",
            (*sets.values(), sid),
        )
