"""문장 카드 — 라이브러리/홈에서 사용."""
from __future__ import annotations

import streamlit as st

from core.db import delete_sentence


def render(s: dict, *, key_prefix: str = "card", show_actions: bool = True) -> None:
    with st.container(border=True):
        st.markdown(s["text"])

        if s.get("note"):
            st.caption(f"📝 {s['note']}")

        meta_bits = []
        if s.get("book_title"):
            meta_bits.append(f"📖 {s['book_title']}")
        if s.get("book_author"):
            meta_bits.append(f"✍️ {s['book_author']}")
        if s.get("page"):
            meta_bits.append(f"p.{s['page']}")
        if s.get("chapter"):
            meta_bits.append(f"ch.{s['chapter']}")
        if meta_bits:
            st.caption(" · ".join(meta_bits))

        tag_names = [t for t in (s.get("tag_names") or "").split(",") if t]
        if tag_names:
            st.markdown(" ".join(f"`#{t}`" for t in tag_names))

        c1, c2, c3, c4 = st.columns([1, 1, 3, 1])
        c1.caption(f"⭐ {s.get('score', 3)}")
        c2.caption(s.get("sentence_type") or "미분류")
        c3.caption((s.get("created_at") or "")[:10])
        if show_actions:
            if c4.button("삭제", key=f"{key_prefix}_del_{s['id']}"):
                delete_sentence(s["id"])
                st.rerun()