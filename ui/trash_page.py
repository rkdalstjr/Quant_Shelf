"""휴지통 — 소프트 삭제된 문장 목록 / 복구. 영구 삭제는 지원하지 않는다."""

from __future__ import annotations

import streamlit as st

from core.db import (
    count_deleted_sentences,
    list_deleted_sentences,
    restore_sentence,
)
from ui.components.cache import invalidate_all  # 캐시 래퍼를 만든 경우에만


def render() -> None:
    st.title("🗑️ 휴지통")
    st.caption(
        "삭제한 문장은 여기 보관됩니다. "
        "**영구 삭제는 지원하지 않습니다** — 실수로 지워도 언제든 복구할 수 있습니다."
    )

    total = count_deleted_sentences()
    if total == 0:
        st.info("휴지통이 비어 있습니다.")
        return

    col_a, col_b = st.columns([1, 4])
    with col_a:
        if st.button(
            f"♻️ 전체 복구 ({total})", type="primary", key="trash_restore_all"
        ):
            _restore_all()

    rows = list_deleted_sentences(limit=500)
    st.caption(f"표시 {len(rows)} / 전체 {total}")

    for r in rows:
        _render_card(r)


def _render_card(s: dict) -> None:
    with st.container(border=True):
        st.markdown(f"~~{s['text']}~~")

        if s.get("note"):
            st.caption(f"📝 {s['note']}")

        meta_bits = []
        if s.get("book_title"):
            meta_bits.append(f"📖 {s['book_title']}")
        if s.get("book_author"):
            meta_bits.append(f"✍️ {s['book_author']}")
        if meta_bits:
            st.caption(" · ".join(meta_bits))

        tag_names = [t for t in (s.get("tag_names") or "").split(",") if t]
        if tag_names:
            st.markdown(" ".join(f"`#{t}`" for t in tag_names))

        deleted = s.get("deleted_at")
        deleted_str = (
            deleted.strftime("%Y-%m-%d %H:%M")
            if hasattr(deleted, "strftime")
            else str(deleted or "")[:16]
        )

        c1, c2 = st.columns([4, 1])
        c1.caption(f"삭제일 {deleted_str}")
        if c2.button("♻️ 복구", key=f"trash_restore_{s['id']}"):
            restore_sentence(s["id"])
            _invalidate()
            st.toast(f"문장 #{s['id']} 복구 완료")
            st.rerun()


def _restore_all() -> None:
    rows = list_deleted_sentences(limit=10**6)
    for r in rows:
        restore_sentence(r["id"])
    _invalidate()
    st.toast(f"{len(rows)}개 복구 완료")
    st.rerun()


def _invalidate() -> None:
    """캐시 래퍼를 도입한 경우에만 호출. 없으면 no-op."""
    try:
        invalidate_all()
    except Exception:
        pass
