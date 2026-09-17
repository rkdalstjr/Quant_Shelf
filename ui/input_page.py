"""문장 입력 페이지."""

from __future__ import annotations

import streamlit as st

from core import dedupe
from core.db import get_or_create_book, insert_sentence
from core.tags import recommend
from ui.components import book_input, tag_input
from core.constants import SENTENCE_TYPES

TYPES = [
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

SAVED_FLAG = "input_just_saved_id"


def render() -> None:
    st.title("📥 문장 입력")
    st.caption("원문은 절대 자동 수정되지 않습니다. 메타데이터만 별도 저장됩니다.")

    # 저장 직후 화면
    if st.session_state.get(SAVED_FLAG):
        sid = st.session_state[SAVED_FLAG]
        st.success(f"저장 완료 · 문장 ID {sid}")
        if st.button("➕ 새 문장 입력"):
            _clear_input_state()
            st.rerun()
        return

    # 1) 원문
    text = st.text_area(
        "원문 문장 *",
        height=180,
        key="in_text",
        placeholder="원서에서 발견한 문장을 붙여넣으세요. (공백 제외 10자 이상)",
    )
    char_count = len((text or "").replace(" ", "").replace("\n", ""))
    st.caption(f"공백 제외 {char_count}자 · 최소 10자")

    # 2) 책/저자
    with st.expander("📚 책 / 저자", expanded=True):
        book = book_input.render("in_book")

    # 3) 태그
    with st.expander("🏷️ 태그", expanded=True):
        tag_ids = tag_input.render("in_tags")

    # 4) 유형 / 중요도
    c1, c2 = st.columns([2, 3])
    with c1:
        sentence_type = st.selectbox("유형", SENTENCE_TYPES, key="in_type")

    with c2:
        score = st.slider("중요도", 1, 5, 3, key="in_score")

    # 5) 메모
    note = st.text_area(
        "메모 (선택)", height=80, key="in_note", placeholder="내 해석, 반례, 관련 경험"
    )

    # 추천 태그 (제안만, 자동 저장 없음)
    if text and len(text) > 20:
        recs = recommend(text)
        if recs:
            st.info(
                "💡 추천 태그: "
                + ", ".join(f"`{r}`" for r in recs)
                + " (제안일 뿐, 자동 저장되지 않습니다)"
            )

    st.divider()

    can_save = char_count >= 10 and bool((book["title"] or book["book_id"]))
    if not can_save:
        st.caption("원문(10자 이상)과 책 제목을 채우면 저장할 수 있습니다.")

    if st.button("💾 저장", type="primary", disabled=not can_save, key="in_save"):
        # 완전 중복 감지
        exact = dedupe.find_exact(text)
        if exact:
            st.error(
                f"동일한 문장이 이미 있습니다 (ID {exact['id']}). "
                "저장을 건너뜁니다. 기존 항목을 확인하세요."
            )
            return

        # 유사 문장 안내 (차단하지 않음)
        similar = dedupe.find_similar(text, threshold=0.7, limit=3)
        if similar:
            with st.expander(
                f"⚠️ 비슷한 문장 {len(similar)}건 (그래도 저장됨)", expanded=False
            ):
                for s in similar:
                    st.caption(f"· {s['text'][:100]}… (유사도 {s['similarity']:.0%})")

        # 책 확보
        book_id = book["book_id"]
        if not book_id:
            book_id = get_or_create_book(
                book["title"],
                book["author"],
                int(book["year"]) if book["year"].isdigit() else None,
            )

        sid = insert_sentence(
            text=text,
            book_id=book_id,
            author=book["author"],
            page=book["page"],
            chapter=book["chapter"],
            sentence_type=sentence_type,
            score=score,
            note=note,
            language="",
            tag_ids=tag_ids,
        )

        st.session_state[SAVED_FLAG] = sid
        st.rerun()


def _clear_input_state() -> None:
    """input 페이지에서 사용한 session_state 키 전부 제거."""
    for k in list(st.session_state.keys()):
        if k.startswith("in_"):
            del st.session_state[k]
    st.session_state.pop(SAVED_FLAG, None)
