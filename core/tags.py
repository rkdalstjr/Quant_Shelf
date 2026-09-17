"""태그 정규화 · 별칭 매핑 · 자동완성 · 추천."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
SEED_PATH = BASE_DIR / "assets" / "tags_seed.yaml"

MAX_LEN = 40

_SEED: Optional[dict] = None


def _load_seed() -> dict:
    global _SEED
    if _SEED is None:
        if SEED_PATH.exists():
            with open(SEED_PATH, encoding="utf-8") as f:
                _SEED = yaml.safe_load(f) or {}
        else:
            _SEED = {}
    return _SEED


def normalize(name: str) -> str:
    """소문자 → 공백→하이픈 → 특수문자 제거 → 중복 하이픈 정리 → 40자 제한."""
    s = (name or "").strip().lower()
    s = s.replace(" ", "-")
    s = re.sub(r"[^\w\-가-힣]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:MAX_LEN]


def resolve_alias(name: str) -> str:
    n = normalize(name)
    aliases = _load_seed().get("aliases", {}) or {}
    return aliases.get(n, n)


def all_seed_tags() -> list[tuple[str, str]]:
    """(tag_name, group) 리스트."""
    out: list[tuple[str, str]] = []
    for group, names in (_load_seed().get("groups", {}) or {}).items():
        for n in names or []:
            out.append((n, group))
    return out


def group_of(tag_name: str) -> str:
    for n, g in all_seed_tags():
        if n == tag_name:
            return g
    return ""


def suggest(prefix: str, existing: list[dict], limit: int = 10) -> list[dict]:
    """existing: list_tags() 결과. 접두 매칭 우선, 그다음 사용빈도."""
    p = normalize(prefix)
    if not p:
        return sorted(existing, key=lambda x: -(x.get("sentence_count") or 0))[:limit]
    hits = [t for t in existing if p in t["name"]]
    hits.sort(
        key=lambda x: (
            not x["name"].startswith(p),  # 접두 매칭 먼저
            -(x.get("sentence_count") or 0),  # 사용빈도
            x["name"],
        )
    )
    return hits[:limit]


def recommend(text: str, limit: int = 5) -> list[str]:
    """문장 키워드와 시드 태그 이름을 단순 매칭."""
    t = (text or "").lower()
    if not t:
        return []
    hits: list[str] = []
    for name, _g in all_seed_tags():
        variants = {name, name.replace("-", " ")}
        if any(v in t for v in variants):
            hits.append(name)
    return hits[:limit]
