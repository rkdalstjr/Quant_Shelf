"""QuantShelf — Streamlit 진입점. 라우팅만 담당."""
import streamlit as st

from core.db import init_db
from ui import home, input_page, library_page

st.set_page_config(page_title="QuantShelf", page_icon="📖", layout="wide")

# 스키마 보장 (매 rerun마다 호출해도 IF NOT EXISTS라 안전)
init_db()

PAGES = {
    "🏠 홈": home.render,
    "📥 문장 입력": input_page.render,
    "📚 라이브러리": library_page.render,
}

with st.sidebar:
    st.markdown("### 📖 QuantShelf")
    page = st.radio("메뉴", list(PAGES.keys()), label_visibility="collapsed")
    st.divider()
    st.caption("v0.1 · 수집 단계")

PAGES[page]()