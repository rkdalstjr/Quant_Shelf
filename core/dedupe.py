"""완전 중복 / 유사 문장 감지. v0.1은 difflib 기반 (외부 ML 미사용)."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from sqlalchemy import text as sql_text  # ← 이름 충돌 방지

from core.db import get_conn


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^\w\s가-힣]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_exact(raw: str) -> Optional[dict]:
    """완전 중복 감지. raw: 사용자가 입력한 원문."""
    key = _norm(raw)
    if not key:
        return None
    with get_conn() as conn:
        rows = conn.execute(
            sql_text("SELECT id, text FROM sentences WHERE deleted_at IS NULL")
        ).fetchall()
    for r in rows:
        # Row → (id, text) 튜플로 접근
        if _norm(r[1]) == key:
            return {"id": r[0], "text": r[1]}
    return None


def find_similar(raw: str, threshold: float = 0.7, limit: int = 5) -> list[dict]:
    key = _norm(raw)
    if not key:
        return []
    out: list[dict] = []
    with get_conn() as conn:
        rows = conn.execute(
            sql_text("SELECT id, text FROM sentences WHERE deleted_at IS NULL")
        ).fetchall()
    for r in rows:
        ratio = SequenceMatcher(None, key, _norm(r[1])).ratio()
        if ratio >= threshold:
            out.append({"id": r[0], "text": r[1], "similarity": ratio})
    out.sort(key=lambda x: -x["similarity"])
    return out[:limit]
