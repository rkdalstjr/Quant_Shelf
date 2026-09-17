"""키워드 + 태그 + 책 + 유형 + 중요도 조합 검색."""
from __future__ import annotations

from typing import Optional

from core.db import get_conn


SORT_MAP = {
    "newest": "s.created_at DESC",
    "oldest": "s.created_at ASC",
    "score":  "s.score DESC, s.created_at DESC",
    "due":    "s.due_date ASC",
}


def search_sentences(
    *,
    keyword: Optional[str] = None,
    tag_ids: Optional[list[int]] = None,
    tag_mode: str = "AND",           # "AND" | "OR"
    book_id: Optional[int] = None,
    sentence_type: Optional[str] = None,
    min_score: Optional[int] = None,
    status: Optional[str] = None,
    sort: str = "newest",
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    where = ["s.deleted_at IS NULL"]
    params: list = []

    if keyword:
        kw = f"%{keyword.strip()}%"
        where.append(
            "(s.text LIKE ? OR s.note LIKE ? OR s.author LIKE ? OR b.title LIKE ?)"
        )
        params.extend([kw, kw, kw, kw])

    if book_id:
        where.append("s.book_id = ?")
        params.append(book_id)

    if sentence_type:
        where.append("s.sentence_type = ?")
        params.append(sentence_type)

    if min_score and min_score > 1:
        where.append("s.score >= ?")
        params.append(min_score)

    if status:
        where.append("s.status = ?")
        params.append(status)

    if tag_ids:
        placeholders = ",".join("?" * len(tag_ids))
        if tag_mode.upper() == "AND":
            where.append(
                f"""s.id IN (
                    SELECT sentence_id FROM sentence_tags
                    WHERE tag_id IN ({placeholders})
                    GROUP BY sentence_id
                    HAVING COUNT(DISTINCT tag_id) = ?
                )"""
            )
            params.extend(tag_ids)
            params.append(len(tag_ids))
        else:
            where.append(
                f"""s.id IN (
                    SELECT sentence_id FROM sentence_tags
                    WHERE tag_id IN ({placeholders})
                )"""
            )
            params.extend(tag_ids)

    order = SORT_MAP.get(sort, SORT_MAP["newest"])

    sql = f"""
        SELECT s.*,
               b.title  AS book_title,
               b.author AS book_author,
               (SELECT GROUP_CONCAT(t.name, ',')
                  FROM tags t
                  JOIN sentence_tags st ON st.tag_id = t.id
                 WHERE st.sentence_id = s.id) AS tag_names
          FROM sentences s
          LEFT JOIN books b ON b.id = s.book_id
         WHERE {' AND '.join(where)}
         ORDER BY {order}
         LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def count_sentences(**kwargs) -> int:
    kwargs.pop("limit", None)
    kwargs.pop("offset", None)
    return len(search_sentences(limit=10**9, **kwargs))