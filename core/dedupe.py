"""완전 중복 / 유사 문장 감지. v0.1은 difflib 기반 (외부 ML 미사용)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import text
from core.db import get_conn


def _norm(text: str) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^\w\s가-힣]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_exact(text: str) -> Optional[dict]:
    key = _norm(text)
    if not key:
        return None
    with get_conn() as conn:
        rows = conn.execute(
            text("SELECT id, text FROM sentences WHERE deleted_at IS NULL")
        ).fetchall()
    for r in rows:
        if _norm(r["text"]) == key:
            return {"id": r["id"], "text": r["text"]}
    return None


def find_similar(text: str, threshold: float = 0.7, limit: int = 5) -> list[dict]:
    key = _norm(text)
    if not key:
        return []
    out: list[dict] = []
    with get_conn() as conn:
        rows = conn.execute(
            text("SELECT id, text FROM sentences WHERE deleted_at IS NULL")
        ).fetchall()
    for r in rows:
        ratio = SequenceMatcher(None, key, _norm(r["text"])).ratio()
        if ratio >= threshold:
            out.append({"id": r["id"], "text": r["text"], "similarity": ratio})
    out.sort(key=lambda x: -x["similarity"])
    return out[:limit]
