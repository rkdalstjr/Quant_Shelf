"""라이브러리 — 수집 문장 검색/필터/정렬."""

from __future__ import annotations

import streamlit as st

from core.db import list_books, list_tags
from core.search import search_sentences
from ui.components import sentence_card

SORT_LABELS = {
    "최신순": "newest",
    "오래된순": "oldest",
    "중요도": "score",
    "복습 임박": "due",
}

TYPE_OPTIONS = [
    "전체",
    "미분류",
    "개념",
    "가정",
    "조언",
    "통찰",
    "시장구조",
    "멘탈모델",
    "반례",
    "커리어",
]


def render() -> None:
    st.title("📚 라이브러리")

    all_tags = list_tags()
    books = list_books()

    with st.sidebar:
        st.subheader("🔎 검색 / 필터")

        keyword = st.text_input(
            "키워드", key="lib_kw", placeholder="문장 · 메모 · 책 · 저자"
        )

        tag_names = sorted([t["name"] for t in all_tags])
        selected_tags = st.multiselect("태그", tag_names, key="lib_tags")
        tag_mode = st.radio(
            "태그 조건", ["AND", "OR"], horizontal=True, key="lib_tag_mode"
        )

        book_options = ["<전체>"] + [b["title"] for b in books]
        book_label = st.selectbox("책", book_options, key="lib_book")
        book_id = None
        if book_label != "<전체>":
            book_id = next((b["id"] for b in books if b["title"] == book_label), None)

        type_label = st.selectbox("유형", TYPE_OPTIONS, key="lib_type")
        sentence_type = None if type_label == "전체" else type_label

        min_score = st.slider("최소 중요도", 1, 5, 1, key="lib_score")

        sort_label = st.selectbox("정렬", list(SORT_LABELS.keys()), key="lib_sort")
        sort = SORT_LABELS[sort_label]

        limit = st.slider("최대 개수", 20, 500, 100, step=20, key="lib_limit")

    name_to_id = {t["name"]: t["id"] for t in all_tags}
    tag_ids = [name_to_id[n] for n in selected_tags if n in name_to_id]

    rows = search_sentences(
        keyword=keyword or None,
        tag_ids=tag_ids or None,
        tag_mode=tag_mode,
        book_id=book_id,
        sentence_type=sentence_type,
        min_score=min_score if min_score > 1 else None,
        sort=sort,
        limit=limit,
    )

    st.caption(f"{len(rows)}개 문장")

    if not rows:
        st.info("조건에 맞는 문장이 없습니다.")
        return

    for s in rows:
        sentence_card.render(s, key_prefix="lib")
