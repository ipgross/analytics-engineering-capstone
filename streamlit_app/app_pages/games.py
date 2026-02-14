"""Games page — Live, Final, and Upcoming NBA games with betting odds."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from styles.theme import inject_css
from queries.games import (
    get_games,
    get_game_results_for_date,
    get_freshness,
    get_available_dates,
    categorize_games,
)
from components.game_card import render_game_card, render_final_card
from components.game_detail import (
    render_game_header,
    render_play_by_play_tab,
    render_matchup_tab,
    render_stats_tab,
)

COLS_PER_ROW = 4


# ── Game detail dialog ─────────────────────────────────────────────────────
@st.dialog("Game Detail", width="large")
def show_game_detail(game: dict):
    """Modal dialog showing expanded game details with tabbed content."""
    render_game_header(game)
    st.divider()
    tabs = st.tabs(["Matchup", "Play-by-Play", "Stats"])
    with tabs[0]:
        render_matchup_tab(game)
    with tabs[1]:
        render_play_by_play_tab(game)
    with tabs[2]:
        render_stats_tab(game)


# ── Custom CSS ──────────────────────────────────────────────────────────────
st.html(inject_css())

# ── Determine available dates ─────────────────────────────────────────────
available_dates = get_available_dates()

# NBA games run past midnight — keep "Today" pinned to the current game-day
# until 6 AM CST so late West Coast finishes aren't prematurely rolled.
_CST = ZoneInfo("America/Chicago")
_now_cst = datetime.now(_CST)
_logical_today = (
    (_now_cst - timedelta(days=1)).date() if _now_cst.hour < 6 else _now_cst.date()
)


def _to_date(d):
    """Coerce a scoreboard date value to datetime.date."""
    if isinstance(d, str):
        return datetime.fromisoformat(d).date()
    return pd.Timestamp(d).date()


def _format_date(d) -> str:
    """Format a date for display (cross-platform)."""
    if d is None:
        return ""
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    try:
        return d.strftime("%A, %B %-d, %Y")
    except ValueError:
        return d.strftime("%A, %B %d, %Y").replace(" 0", " ")


def _format_date_short(d) -> str:
    """Format a date as 'Fri, Feb 14' (cross-platform)."""
    if d is None:
        return ""
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    try:
        return d.strftime("%A, %B %-d")
    except ValueError:
        return d.strftime("%A, %B %d").replace(" 0", " ")


# Match scoreboard dates to Today/Yesterday
today_raw = None
yesterday_raw = None
for d in available_dates:
    dd = _to_date(d)
    if dd == _logical_today:
        today_raw = d
    elif dd == _logical_today - timedelta(days=1):
        yesterday_raw = d

# Upcoming dates: anything after today in the scoreboard
upcoming_raw = [d for d in available_dates if _to_date(d) > _logical_today]


# ── Freshness indicator ──────────────────────────────────────────────────
freshness = get_freshness()
last_update = freshness["last_update"]

if last_update is not None:
    if isinstance(last_update, str):
        last_dt = datetime.fromisoformat(last_update).replace(tzinfo=timezone.utc)
    else:
        last_dt = last_update.replace(tzinfo=timezone.utc)
    delta_secs = (datetime.now(timezone.utc) - last_dt).total_seconds()
    if delta_secs < 120:
        fresh_text = "Updated just now"
        fresh_cls = "freshness"
    elif delta_secs < 300:
        fresh_text = f"Updated {int(delta_secs / 60)}m ago"
        fresh_cls = "freshness"
    else:
        fresh_text = f"Updated {int(delta_secs / 60)}m ago"
        fresh_cls = "freshness stale"
else:
    fresh_text = "No data"
    fresh_cls = "freshness stale"

# ── Header row: title + date + controls + freshness (all inline) ─────────
hdr_title, hdr_date, hdr_market, hdr_fresh = st.columns([3, 2.5, 2, 1.5])

with hdr_date:
    selected_label = st.segmented_control(
        "Date",
        options=["Today", "Upcoming", "Yesterday"],
        default="Today",
        label_visibility="collapsed",
    )

with hdr_market:
    MARKET_OPTIONS = ["Spreads", "H2H", "Totals"]
    MARKET_MAP = {"Spreads": "spreads", "H2H": "h2h", "Totals": "totals"}
    market = st.segmented_control(
        "Market",
        options=MARKET_OPTIONS,
        default="Spreads",
        label_visibility="collapsed",
    )
    market_key = MARKET_MAP.get(market, "spreads")

# Determine header date display
if selected_label == "Today":
    date_display = _format_date(_logical_today)
elif selected_label == "Upcoming":
    date_display = "Next 7 Days"
else:
    date_display = _format_date(
        _logical_today - timedelta(days=1)
    )

with hdr_title:
    st.markdown(
        f'<div class="page-header">'
        f'<h2>NBA Games</h2>'
        f'<span style="color:#9CA3AF;font-size:0.85rem;">{date_display}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

with hdr_fresh:
    st.markdown(
        f'<div style="text-align:right;padding-top:0.5rem;">'
        f'<span class="{fresh_cls}">{fresh_text}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Helper: render a grid of cards with even spacing ───────────────────
def _render_card_grid(cards: list[tuple[str, dict]]):
    """Render cards in a fixed-width grid with detail buttons.

    Args:
        cards: List of (html_string, game_dict) tuples.
    """
    for i in range(0, len(cards), COLS_PER_ROW):
        cols = st.columns(COLS_PER_ROW)
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(cards):
                html, game = cards[idx]
                col.markdown(html, unsafe_allow_html=True)
                if col.button(
                    "Details",
                    key=f"detail_{game['GAME_ID']}_{selected_label}",
                    width="stretch",
                ):
                    st.session_state["selected_game"] = game
                    st.rerun()


# ── Render helpers for each view ──────────────────────────────────────────

def _render_today_view():
    """Render Today: UPCOMING -> LIVE -> FINAL for today's date."""
    if today_raw is None:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No games scheduled for today</h3>"
            "<p>Check the Upcoming tab for the next games</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    df = get_games(market_key, game_date=today_raw)
    if df.empty:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No games scheduled for today</h3>"
            "<p>Check the Upcoming tab for the next games</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    sections = categorize_games(df)

    upcoming_df = sections["upcoming"]
    if not upcoming_df.empty:
        st.markdown('<div class="section-header">UPCOMING</div>', unsafe_allow_html=True)
        cards = []
        for i in range(len(upcoming_df)):
            game = upcoming_df.iloc[i].to_dict()
            cards.append((render_game_card(game, market_key, "upcoming"), game))
        _render_card_grid(cards)

    live_df = sections["live"]
    if not live_df.empty:
        st.markdown('<div class="section-header live">LIVE</div>', unsafe_allow_html=True)
        cards = []
        for i in range(len(live_df)):
            game = live_df.iloc[i].to_dict()
            cards.append((render_game_card(game, market_key, "live"), game))
        _render_card_grid(cards)

    final_df = sections["final"]
    if not final_df.empty:
        st.markdown('<div class="section-header">FINAL</div>', unsafe_allow_html=True)
        results_map = get_game_results_for_date(today_raw)

        cards = []
        for i in range(len(final_df)):
            game = final_df.iloc[i].to_dict()
            key = (game["GAME_DATE"], game["HOME_TEAM_NAME"])
            result = results_map.get(key)
            cards.append((render_final_card(game, result, market_key), game))
        _render_card_grid(cards)


def _render_upcoming_view():
    """Render Upcoming: games grouped by date for the next 7 days."""
    if not upcoming_raw:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No upcoming games in the scoreboard</h3>"
            "<p>Games are loaded by the upcoming ingestion pipeline</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Fetch all games (no date filter) and filter to future dates
    df = get_games(market_key)
    if df.empty:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No upcoming games available</h3>"
            "<p>Games are loaded by the upcoming ingestion pipeline</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    df = df[df["GAME_DATE"].apply(lambda d: _to_date(d) > _logical_today)].copy()
    if df.empty:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No upcoming games available</h3>"
            "<p>Games are loaded by the upcoming ingestion pipeline</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Group by date and render with date headers
    for game_date, date_group in df.groupby("GAME_DATE", sort=True):
        date_header = _format_date_short(game_date)
        st.markdown(
            f'<div class="section-header">{date_header}</div>',
            unsafe_allow_html=True,
        )

        sections = categorize_games(date_group)

        # Upcoming (not started) — show with date on card
        upcoming_df = sections["upcoming"]
        if not upcoming_df.empty:
            cards = []
            for i in range(len(upcoming_df)):
                game = upcoming_df.iloc[i].to_dict()
                cards.append((
                    render_game_card(game, market_key, "upcoming", show_date=True),
                    game,
                ))
            _render_card_grid(cards)

        # Live games on future dates (edge case: games in progress)
        live_df = sections["live"]
        if not live_df.empty:
            cards = []
            for i in range(len(live_df)):
                game = live_df.iloc[i].to_dict()
                cards.append((render_game_card(game, market_key, "live"), game))
            _render_card_grid(cards)

        # Final games on future dates (edge case: completed games)
        final_df = sections["final"]
        if not final_df.empty:
            results_map = get_game_results_for_date(game_date)
            cards = []
            for i in range(len(final_df)):
                game = final_df.iloc[i].to_dict()
                key = (game["GAME_DATE"], game["HOME_TEAM_NAME"])
                result = results_map.get(key)
                cards.append((render_final_card(game, result, market_key), game))
            _render_card_grid(cards)


def _render_yesterday_view():
    """Render Yesterday: only FINAL section with betting results."""
    if yesterday_raw is None:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No games from yesterday</h3>"
            "<p>Yesterday\'s results are not in the scoreboard</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    df = get_games(market_key, game_date=yesterday_raw)
    if df.empty:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No games from yesterday</h3>"
            "<p>Results appear after games finish</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    sections = categorize_games(df)
    final_df = sections["final"]
    if final_df.empty:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No completed games</h3>"
            "<p>Results appear after games finish</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    st.markdown('<div class="section-header">FINAL</div>', unsafe_allow_html=True)
    results_map = get_game_results_for_date(yesterday_raw)

    cards = []
    for i in range(len(final_df)):
        game = final_df.iloc[i].to_dict()
        key = (game["GAME_DATE"], game["HOME_TEAM_NAME"])
        result = results_map.get(key)
        cards.append((render_final_card(game, result, market_key), game))
    _render_card_grid(cards)


# ── Auto-refresh fragment for live data ─────────────────────────────────
@st.fragment(run_every="60s")
def games_board():
    """Fetch and render game sections based on selected tab. Re-runs every 60s."""
    if selected_label == "Today":
        _render_today_view()
    elif selected_label == "Upcoming":
        _render_upcoming_view()
    else:
        _render_yesterday_view()


games_board()

# ── Dialog trigger (page level, outside fragment) ─────────────────────────
if st.session_state.get("selected_game") is not None:
    game = st.session_state.pop("selected_game")
    show_game_detail(game)
