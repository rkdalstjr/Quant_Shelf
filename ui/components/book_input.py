"""책/저자 입력 위젯 — 기존 책 selectbox + 신규 등록 필드."""
from __future__ import annotations

import streamlit as st

from core.db import list_books

NEW_BOOK = "➕ 새 책 등록"


def render(key: str) -> dict:
    """{book_id, title, author, year, page, chapter} 반환.

    신규 책일 때는 book_id=None. 저장 시점에 get_or_create_book 호출.
    """
    books = list_books()
    titles = [NEW_BOOK] + [b["title"] for b in books]

    selected = st.selectbox("책 제목 *", titles, key=f"{key}_title")

    book_id = None
    year = ""
    if selected == NEW_BOOK:
        title = st.text_input("새 책 제목 *", key=f"{key}_new_title")
        author = st.text_input("저자", key=f"{key}_new_author")
        year = st.text_input("출판연도 (선택)", key=f"{key}_year")
    else:
        b = next((x for x in books if x["title"] == selected), None)
        book_id = b["id"] if b else None
        title = selected
        author = st.text_input(
            "저자",
            value=(b["author"] if b else "") or "",
            key=f"{key}_author",
        )
        if b:
            st.caption(f"기존 책 · 수집 문장 {b['sentence_count']}개")

    c1, c2 = st.columns(2)
    with c1:
        page = st.text_input("페이지 (선택)", key=f"{key}_page")
    with c2:
        chapter = st.text_input("챕터 (선택)", key=f"{key}_chapter")

    return {
        "book_id": book_id,
        "title": (title or "").strip(),
        "author": (author or "").strip(),
        "year": (year or "").strip(),
        "page": (page or "").strip(),
        "chapter": (chapter or "").strip(),
    }