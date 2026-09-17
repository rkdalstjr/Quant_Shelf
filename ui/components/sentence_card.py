"""문장 카드 — 라이브러리/홈에서 사용. 편집 모드 내장."""

from __future__ import annotations

import streamlit as st

from core import dedupe
from core.constants import SENTENCE_TYPES
from core.db import (
    delete_sentence,
    get_or_create_book,
    get_sentence,
    set_sentence_tags,
    update_sentence,
)
from ui.components import book_input, tag_input

EDIT_KEY = "editing_sentence_id"


def _clear_edit_state(sid: int) -> None:
    """해당 문장의 편집용 session_state 키 전부 제거."""
    prefix = f"edit_{sid}_"
    for k in list(st.session_state.keys()):
        if k.startswith(prefix):
            del st.session_state[k]
    if st.session_state.get(EDIT_KEY) == sid:
        st.session_state.pop(EDIT_KEY, None)


def render(s: dict, *, key_prefix: str = "card", show_actions: bool = True) -> None:
    sid = s["id"]

    # 이 카드가 편집 중이면 편집 폼 렌더
    if st.session_state.get(EDIT_KEY) == sid:
        _render_edit_form(s)
        return

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

        c1, c2, c3, c4, c5 = st.columns([1, 2, 4, 1, 1])
        c1.caption(f"⭐ {s.get('score', 3)}")
        c2.caption(s.get("sentence_type") or "미분류")
        c3.caption((s.get("created_at") or "")[:10])
        if show_actions:
            if c4.button("✏️", key=f"{key_prefix}_edit_{sid}", help="수정"):
                st.session_state[EDIT_KEY] = sid
                st.rerun()
            if c5.button("🗑️", key=f"{key_prefix}_del_{sid}", help="삭제"):
                delete_sentence(sid)
                st.rerun()


# --------------------------------------------------------------------------- 편집 폼


def _render_edit_form(s: dict) -> None:
    sid = s["id"]
    full = get_sentence(sid) or s  # 태그 id 리스트 포함 최신본
    current_tag_ids = [t["id"] for t in full.get("tags", [])]

    with st.container(border=True):
        st.markdown("#### ✏️ 문장 수정")
        st.caption("원문은 여기서만 바뀝니다. 저장 전에는 DB에 반영되지 않습니다.")

        # 1) 원문
        new_text = st.text_area(
            "원문 *",
            value=full["text"],
            height=150,
            key=f"edit_{sid}_text",
        )
        char_count = len((new_text or "").replace(" ", "").replace("\n", ""))
        st.caption(f"공백 제외 {char_count}자 · 최소 10자")

        # 2) 책/저자
        with st.expander("📚 책 / 저자", expanded=True):
            book = book_input.render(
                f"edit_{sid}_book",
                default_book_id=full.get("book_id"),
            )

        # 3) 태그
        with st.expander("🏷️ 태그", expanded=True):
            tag_ids = tag_input.render(
                f"edit_{sid}_tags",
                default_ids=current_tag_ids,
            )

        # 4) 유형/중요도
        current_type = full.get("sentence_type") or "미분류"
        type_idx = (
            SENTENCE_TYPES.index(current_type) if current_type in SENTENCE_TYPES else 0
        )
        c1, c2 = st.columns([2, 3])
        with c1:
            sentence_type = st.selectbox(
                "유형", SENTENCE_TYPES, index=type_idx, key=f"edit_{sid}_type"
            )
        with c2:
            score = st.slider(
                "중요도", 1, 5, int(full.get("score") or 3), key=f"edit_{sid}_score"
            )

        # 5) 메모
        note = st.text_area(
            "메모 (선택)",
            value=full.get("note") or "",
            height=80,
            key=f"edit_{sid}_note",
        )

        st.divider()
        c_save, c_cancel = st.columns([1, 1])

        with c_save:
            if st.button("💾 저장", type="primary", key=f"edit_{sid}_save"):
                _handle_save(
                    sid=sid,
                    new_text=new_text,
                    book=book,
                    tag_ids=tag_ids,
                    sentence_type=sentence_type,
                    score=score,
                    note=note,
                )

        with c_cancel:
            if st.button("취소", key=f"edit_{sid}_cancel"):
                _clear_edit_state(sid)
                st.rerun()


def _handle_save(
    *,
    sid: int,
    new_text: str,
    book: dict,
    tag_ids: list[int],
    sentence_type: str,
    score: int,
    note: str,
) -> None:
    # 검증 1) 최소 길이
    stripped = (new_text or "").replace(" ", "").replace("\n", "")
    if len(stripped) < 10:
        st.error("원문은 공백 제외 10자 이상이어야 합니다.")
        return

    # 검증 2) 완전 중복 (자기 자신 제외)
    exact = dedupe.find_exact(new_text)
    if exact and exact["id"] != sid:
        st.error(
            f"동일한 문장이 이미 있습니다 (ID {exact['id']}). "
            "다른 문장과 완전히 겹칩니다."
        )
        return

    # 유사 문장 경고 (차단하지 않음)
    similar = [
        x
        for x in dedupe.find_similar(new_text, threshold=0.7, limit=3)
        if x["id"] != sid
    ]
    if similar:
        st.warning(
            "비슷한 문장이 있습니다: "
            + ", ".join(f"ID {x['id']}" for x in similar)
            + " (그래도 저장됩니다)"
        )

    # 책 확보
    book_id = book["book_id"]
    if not book_id:
        if not book["title"]:
            st.error("책 제목이 필요합니다.")
            return
        book_id = get_or_create_book(
            book["title"],
            book["author"],
            int(book["year"]) if book["year"].isdigit() else None,
        )

    # 업데이트
    update_sentence(
        sid,
        text=new_text,
        book_id=book_id,
        author=book["author"],
        page=book["page"],
        chapter=book["chapter"],
        sentence_type=sentence_type,
        score=score,
        note=note,
    )
    set_sentence_tags(sid, tag_ids)

    _clear_edit_state(sid)
    st.toast(f"문장 #{sid} 수정 완료")
    st.rerun()
