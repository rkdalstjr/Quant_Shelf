"""태그 입력 위젯 — 기존 태그 multiselect + 새 태그 등록."""
from __future__ import annotations

import streamlit as st

from core import tags as tag_mod
from core.db import get_or_create_tag, list_tags


def render(key: str, default_ids: list[int] | None = None) -> list[int]:
    """선택된 태그 ID 리스트를 반환."""
    all_tags = list_tags()
    name_to_id = {t["name"]: t["id"] for t in all_tags}
    id_to_name = {t["id"]: t["name"] for t in all_tags}

    ms_key = f"{key}_ms"
    pending_key = f"{key}_pending"

    # 1) 이전 run에서 예약된 추가를 위젯 생성 "전에" 반영
    pending = st.session_state.get(pending_key)
    if pending:
        current = list(st.session_state.get(ms_key, []))
        if pending not in current:
            current.append(pending)
        st.session_state[ms_key] = current
        st.session_state[pending_key] = None

    # 2) 초기값 설정 / 옵션에서 사라진 이름 정리
    if ms_key not in st.session_state:
        st.session_state[ms_key] = [
            id_to_name[t] for t in (default_ids or []) if t in id_to_name
        ]
    else:
        st.session_state[ms_key] = [
            n for n in st.session_state[ms_key] if n in name_to_id
        ]

    selected_names = st.multiselect(
        "태그 (기존에서 선택)",
        options=sorted(name_to_id.keys()),
        key=ms_key,
        help="여러 개 선택 가능. 새 태그는 아래에서 등록하세요.",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        new_tag = st.text_input(
            "새 태그 등록",
            key=f"{key}_new",
            placeholder="예: risk-management, 변동성",
        )
    with col2:
        new_group = st.text_input(
            "그룹(선택)", key=f"{key}_grp", placeholder="finance"
        )

    if new_tag:
        resolved = tag_mod.resolve_alias(new_tag)
        if not resolved:
            st.caption("유효한 태그 이름을 입력하세요.")
        elif resolved in name_to_id:
            st.caption(f"`{resolved}`은(는) 이미 존재합니다. 위 목록에서 선택하세요.")
        else:
            grp = new_group.strip() or tag_mod.group_of(resolved)
            if st.button(f"➕ '{resolved}' 등록", key=f"{key}_addbtn"):
                get_or_create_tag(resolved, tag_group=grp)
                st.session_state[pending_key] = resolved
                st.rerun()

    # 현재 선택 상태 기반 ID 리스트 반환
    return [name_to_id[n] for n in st.session_state.get(ms_key, []) if n in name_to_id]