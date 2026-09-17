"""DB 연결 · 스키마 · CRUD — SQLite(로컬) / PostgreSQL(클라우드) 자동 전환."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Optional

import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_DB_PATH = BASE_DIR / "data" / "quantshelf.db"
LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- 엔진 선택


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    """secrets.toml에 URL이 있으면 그걸 쓰고, 없으면 로컬 SQLite."""
    try:
        url = st.secrets["connections"]["quantshelf_db"]["url"]
    except (KeyError, FileNotFoundError):
        url = f"sqlite:///{LOCAL_DB_PATH}"

    # SQLite는 스레드 체크 해제 (Streamlit 멀티스레드 대응)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, poolclass=NullPool)


@contextmanager
def get_conn():
    """SQLAlchemy 연결을 dict-like Row로 다루는 컨텍스트."""
    engine = get_engine()
    with engine.begin() as conn:
        yield conn


# --------------------------------------------------------------------------- 스키마

# SQLite/PostgreSQL 양쪽에서 동작하도록 AUTOINCREMENT 대신 SERIAL 계열 사용
SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS books (
        id          SERIAL PRIMARY KEY,
        title       TEXT NOT NULL UNIQUE,
        author      TEXT DEFAULT '',
        year        INTEGER,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS tags (
        id          SERIAL PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,
        tag_group   TEXT DEFAULT '',
        aliases     TEXT DEFAULT '',
        description TEXT DEFAULT '',
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS sentences (
        id              SERIAL PRIMARY KEY,
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
        due_date        TIMESTAMP,
        lapses          INTEGER DEFAULT 0,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        deleted_at      TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS sentence_tags (
        sentence_id INTEGER NOT NULL REFERENCES sentences(id) ON DELETE CASCADE,
        tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (sentence_id, tag_id)
    )""",
    "CREATE INDEX IF NOT EXISTS idx_sentences_book   ON sentences(book_id)",
    "CREATE INDEX IF NOT EXISTS idx_sentences_due    ON sentences(due_date)",
    "CREATE INDEX IF NOT EXISTS idx_sentences_status ON sentences(status)",
    "CREATE INDEX IF NOT EXISTS idx_st_tag           ON sentence_tags(tag_id)",
]


def init_db() -> None:
    with get_conn() as conn:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(text(stmt))


def _rows(result) -> list[dict]:
    out = []
    for r in result:
        d = dict(r._mapping)
        for k, v in d.items():
            if hasattr(v, "isoformat"):  # datetime, date
                d[k] = v.isoformat(sep=" ", timespec="seconds")
        out.append(d)
    return out


# --------------------------------------------------------------------------- books


def get_or_create_book(title: str, author: str = "", year: Optional[int] = None) -> int:
    title = (title or "").strip()
    if not title:
        raise ValueError("book title is required")
    author = (author or "").strip()

    with get_conn() as conn:
        row = conn.execute(
            text("SELECT id FROM books WHERE title = :t"), {"t": title}
        ).fetchone()
        if row:
            if author:
                conn.execute(
                    text(
                        "UPDATE books SET author = :a WHERE id = :i AND (author IS NULL OR author = '')"
                    ),
                    {"a": author, "i": row[0]},
                )
            return row[0]

        # PostgreSQL은 RETURNING, SQLite는 lastrowid — 양쪽 호환
        result = conn.execute(
            text(
                "INSERT INTO books (title, author, year) VALUES (:t, :a, :y) RETURNING id"
            ),
            {"t": title, "a": author, "y": year},
        )
        return result.scalar()


@st.cache_data(ttl=30, show_spinner=False)
def list_books() -> list[dict]:
    sql = text("""
        SELECT b.id, b.title, b.author, b.year,
               COUNT(s.id) AS sentence_count
          FROM books b
          LEFT JOIN sentences s
            ON s.book_id = b.id AND s.deleted_at IS NULL
         GROUP BY b.id, b.title, b.author, b.year
         ORDER BY sentence_count DESC, b.title
    """)
    with get_conn() as conn:
        return _rows(conn.execute(sql))


# --------------------------------------------------------------------------- tags


def get_or_create_tag(name: str, tag_group: str = "", aliases: str = "") -> int:
    name = (name or "").strip()
    if not name:
        raise ValueError("tag name is required")
    with get_conn() as conn:
        row = conn.execute(
            text("SELECT id FROM tags WHERE name = :n"), {"n": name}
        ).fetchone()
        if row:
            return row[0]
        result = conn.execute(
            text(
                "INSERT INTO tags (name, tag_group, aliases) VALUES (:n, :g, :a) RETURNING id"
            ),
            {"n": name, "g": tag_group or "", "a": aliases or ""},
        )
        return result.scalar()


@st.cache_data(ttl=30, show_spinner=False)
def list_tags() -> list[dict]:
    sql = text("""
        SELECT t.id, t.name, t.tag_group,
               COUNT(s.id) AS sentence_count
          FROM tags t
          LEFT JOIN sentence_tags st ON st.tag_id = t.id
          LEFT JOIN sentences s
            ON s.id = st.sentence_id AND s.deleted_at IS NULL
         GROUP BY t.id, t.name, t.tag_group
         ORDER BY sentence_count DESC, t.name
    """)
    with get_conn() as conn:
        return _rows(conn.execute(sql))


# --------------------------------------------------------------------------- sentences


def insert_sentence(
    *,
    text_content: str,
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
    sql = text("""
        INSERT INTO sentences
            (text, book_id, author, page, chapter,
             sentence_type, score, note, language, due_date)
        VALUES (:txt, :bid, :auth, :page, :ch,
                :stype, :score, :note, :lang,
                CURRENT_TIMESTAMP + INTERVAL '1 day')
        RETURNING id
    """)
    # SQLite는 INTERVAL 미지원 → 별도 분기
    is_sqlite = get_engine().dialect.name == "sqlite"
    if is_sqlite:
        sql = text("""
            INSERT INTO sentences
                (text, book_id, author, page, chapter,
                 sentence_type, score, note, language, due_date)
            VALUES (:txt, :bid, :auth, :page, :ch,
                    :stype, :score, :note, :lang,
                    datetime('now', '+1 day'))
            RETURNING id
        """)

    params = {
        "txt": text_content,
        "bid": book_id,
        "auth": author,
        "page": page,
        "ch": chapter,
        "stype": sentence_type,
        "score": score,
        "note": note,
        "lang": language,
    }
    with get_conn() as conn:
        sid = conn.execute(sql, params).scalar()
        for tid in tag_ids:
            conn.execute(
                text(
                    "INSERT INTO sentence_tags (sentence_id, tag_id) VALUES (:s, :t) ON CONFLICT DO NOTHING"
                ),
                {"s": sid, "t": tid},
            )
        return sid


def get_sentence(sid: int) -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            text("SELECT * FROM sentences WHERE id = :i AND deleted_at IS NULL"),
            {"i": sid},
        ).fetchone()
        if not row:
            return None
        d = dict(row._mapping)
        d["tags"] = _rows(
            conn.execute(
                text("""
            SELECT t.id, t.name, t.tag_group
              FROM tags t
              JOIN sentence_tags st ON st.tag_id = t.id
             WHERE st.sentence_id = :i
             ORDER BY t.name
        """),
                {"i": sid},
            )
        )
        if d.get("book_id"):
            b = conn.execute(
                text("SELECT title, author FROM books WHERE id = :i"),
                {"i": d["book_id"]},
            ).fetchone()
            d["book_title"] = b[0] if b else ""
            d["book_author"] = b[1] if b else ""
        else:
            d["book_title"] = ""
            d["book_author"] = ""
        return d


def delete_sentence(sid: int) -> None:
    with get_conn() as conn:
        conn.execute(
            text(
                "UPDATE sentences SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = :i"
            ),
            {"i": sid},
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
    cols = ", ".join(f"{k} = :{k}" for k in sets)
    params = dict(sets)
    params["sid"] = sid
    with get_conn() as conn:
        conn.execute(
            text(
                f"UPDATE sentences SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = :sid"
            ),
            params,
        )


def set_sentence_tags(sid: int, tag_ids: Iterable[int]) -> None:
    with get_conn() as conn:
        conn.execute(
            text("DELETE FROM sentence_tags WHERE sentence_id = :i"), {"i": sid}
        )
        for tid in tag_ids:
            conn.execute(
                text(
                    "INSERT INTO sentence_tags (sentence_id, tag_id) VALUES (:s, :t) ON CONFLICT DO NOTHING"
                ),
                {"s": sid, "t": tid},
            )
