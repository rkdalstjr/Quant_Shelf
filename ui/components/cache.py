"""core 함수를 UI에서 캐시하는 래퍼."""

from __future__ import annotations

import streamlit as st

from core.db import list_books, list_tags
from core.search import search_sentences


@st.cache_data(ttl=30, show_spinner=False)
def cached_books() -> list[dict]:
    return list_books()


@st.cache_data(ttl=30, show_spinner=False)
def cached_tags() -> list[dict]:
    return list_tags()


@st.cache_data(ttl=15, show_spinner=False)
def cached_search(**kwargs) -> list[dict]:
    return search_sentences(**kwargs)


def invalidate_all() -> None:
    cached_books.clear()
    cached_tags.clear()
    cached_search.clear()
