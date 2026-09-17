"""홈/대시보드."""
from __future__ import annotations

import streamlit as st

from core.db import list_books, list_tags
from core.search import search_sentences
from ui.components import sentence_card


def render() -> None:
    st.title("📖 QuantShelf")
    st.caption("문장 수집 → 태그 메타데이터 → (예정) SRS · 퀴즈 · TTS · 통계")

    recent = search_sentences(sort="newest", limit=200)
    books = list_books()
    tags = list_tags()

    c1, c2, c3 = st.columns(3)
    c1.metric("수집 문장", len(recent))
    c2.metric("책", len(books))
    c3.metric("태그", len(tags))

    st.divider()
    st.subheader("최근 추가 문장")
    if not recent:
        st.info("아직 문장이 없습니다. 좌측 메뉴의 **📥 문장 입력**에서 시작하세요.")
        return

    for s in recent[:8]:
        sentence_card.render(s, key_prefix="home", show_actions=False)

    st.divider()
    st.subheader("태그 상위")
    top_tags = [t for t in tags if (t.get("sentence_count") or 0) > 0][:20]
    if top_tags:
        st.markdown(
            " ".join(f"`#{t['name']}` <sub>{t['sentence_count']}</sub>" for t in top_tags),
            unsafe_allow_html=True,
        )
    else:
        st.caption("태그가 아직 없습니다.")