"""키워드 + 태그 + 책 + 유형 + 중요도 조합 검색."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import text

from core.db import get_conn, _rows

SORT_MAP = {
    "newest": "s.created_at DESC",
    "oldest": "s.created_at ASC",
    "score": "s.score DESC, s.created_at DESC",
    "due": "s.due_date ASC",
}


def search_sentences(
    *,
    keyword: Optional[str] = None,
    tag_ids: Optional[list[int]] = None,
    tag_mode: str = "AND",
    book_id: Optional[int] = None,
    sentence_type: Optional[str] = None,
    min_score: Optional[int] = None,
    status: Optional[str] = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    where = ["s.deleted_at IS NULL"]
    params: dict = {}

    if keyword:
        where.append(
            "(s.text LIKE :kw OR s.note LIKE :kw OR s.author LIKE :kw OR b.title LIKE :kw)"
        )
        params["kw"] = f"%{keyword.strip()}%"

    if book_id:
        where.append("s.book_id = :bid")
        params["bid"] = book_id

    if sentence_type:
        where.append("s.sentence_type = :stype")
        params["stype"] = sentence_type

    if min_score and min_score > 1:
        where.append("s.score >= :mscore")
        params["mscore"] = min_score

    if status:
        where.append("s.status = :status")
        params["status"] = status

    if tag_ids:
        if tag_mode.upper() == "AND":
            where.append("""s.id IN (
                    SELECT sentence_id FROM sentence_tags
                     WHERE tag_id IN :tag_ids
                     GROUP BY sentence_id
                    HAVING COUNT(DISTINCT tag_id) = :tag_count
                )""")
            params["tag_count"] = len(tag_ids)
        else:
            where.append(
                "s.id IN (SELECT sentence_id FROM sentence_tags WHERE tag_id IN :tag_ids)"
            )
        # SQLAlchemy expanding bindparam 처리용 tuple
        params["tag_ids"] = tuple(tag_ids) if len(tag_ids) > 1 else (tag_ids[0],)

    order = SORT_MAP.get(sort, SORT_MAP["newest"])

    sql = text(f"""
        SELECT s.id, s.text, s.book_id, s.author, s.page, s.chapter,
               s.sentence_type, s.score, s.note, s.language, s.status,
               s.ease, s.interval_days, s.repetitions, s.due_date,
               s.lapses, s.created_at, s.updated_at, s.deleted_at,
               b.title  AS book_title,
               b.author AS book_author
          FROM sentences s
          LEFT JOIN books b ON b.id = s.book_id
         WHERE {' AND '.join(where)}
         ORDER BY {order}
         LIMIT :limit OFFSET :offset
    """)
    params["limit"] = limit
    params["offset"] = offset

    with get_conn() as conn:
        rows = [dict(r._mapping) for r in conn.execute(sql, params)]
        if not rows:
            return []

        sids = [r["id"] for r in rows]
        placeholders = ",".join(f":s{i}" for i in range(len(sids)))
        tag_params = {f"s{i}": sid for i, sid in enumerate(sids)}
        tag_rows = conn.execute(
            text(f"""
                SELECT st.sentence_id, t.name
                FROM tags t
                JOIN sentence_tags st ON st.tag_id = t.id
                WHERE st.sentence_id IN ({placeholders})
                ORDER BY t.name
            """),
            tag_params,
        ).fetchall()

        by_sid: dict[int, list[str]] = {}
        for sid, name in tag_rows:
            by_sid.setdefault(sid, []).append(name)

        for r in rows:
            r["tag_names"] = ",".join(by_sid.get(r["id"], []))
        return rows


def count_sentences(**kwargs) -> int:
    kwargs.pop("limit", None)
    kwargs.pop("offset", None)
    return len(search_sentences(limit=10**9, **kwargs))
