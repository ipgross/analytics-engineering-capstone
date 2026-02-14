"""NBA Live Analytics — Streamlit multipage app entrypoint."""

import streamlit as st

st.set_page_config(
    page_title="THE COVER",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Pages ───────────────────────────────────────────────────────────────────
games_page = st.Page(
    "app_pages/games.py",
    title="Games",
    icon=":material/sports_basketball:",
    default=True,
)
predictions_page = st.Page(
    "app_pages/predictions.py",
    title="Predictions",
    icon=":material/query_stats:",
)
odds_page = st.Page(
    "app_pages/odds.py",
    title="Odds",
    icon=":material/trending_up:",
)
grades_page = st.Page(
    "app_pages/grades.py",
    title="Grades",
    icon=":material/grade:",
)
records_page = st.Page(
    "app_pages/records.py",
    title="Records",
    icon=":material/leaderboard:",
)
matchups_page = st.Page(
    "app_pages/matchups.py",
    title="Matchups",
    icon=":material/compare_arrows:",
)

pg = st.navigation(
    {
        "Live": [games_page],
        "Analytics": [predictions_page, odds_page],
        "History": [grades_page, records_page, matchups_page],
    }
)

# ── Sidebar branding (below nav) ────────────────────────────────────────────
st.sidebar.markdown(
    '<div class="sidebar-brand">THE COVER</div>',
    unsafe_allow_html=True,
)

pg.run()
