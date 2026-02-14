"""Predictions page — Two-panel layout with game list and full prediction detail."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from styles.theme import inject_css
from queries.predictions import (
    get_predictions_all_markets,
    get_best_bets,
    categorize_predictions,
    get_freshness,
)
from components.predictions_table import render_best_bets_strip
from components.prediction_detail import render_all_markets_prediction
from data.teams import get_team_abbrev, get_logo_url

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.html(inject_css())

# ── Date logic (6am CST rollover) ───────────────────────────────────────────
_CST = ZoneInfo("America/Chicago")
_now_cst = datetime.now(_CST)
_logical_today = (
    (_now_cst - timedelta(days=1)).date() if _now_cst.hour < 6 else _now_cst.date()
)


def _format_date(d) -> str:
    """Format a date for display (cross-platform safe)."""
    if d is None:
        return ""
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    try:
        return d.strftime("%A, %B %-d, %Y")
    except ValueError:
        return d.strftime("%A, %B %d, %Y").replace(" 0", " ")


# ── Freshness indicator ─────────────────────────────────────────────────────
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

# ── Header row: title | date toggle | freshness ─────────────────────────
hdr_title, hdr_date, hdr_fresh = st.columns([3, 3, 1.5])

with hdr_date:
    selected_date_label = st.segmented_control(
        "Date",
        options=["Today", "Upcoming", "Pick a Date"],
        default="Today",
        label_visibility="collapsed",
        key="pred_date_toggle",
    )

# Derive query mode
_mode_map = {"Today": "today", "Upcoming": "upcoming", "Pick a Date": "pick_a_date"}
query_mode = _mode_map.get(selected_date_label, "today")

# Conditional date picker (outside fragment — triggers full rerun)
picked_date = None
if selected_date_label == "Pick a Date":
    picked_date = st.date_input(
        "Select date",
        value=_logical_today,
        min_value=_logical_today - timedelta(days=30),
        max_value=_logical_today + timedelta(days=7),
        label_visibility="collapsed",
        key="pred_date_picker",
    )

# Date display text
if selected_date_label == "Today":
    date_display = _format_date(_logical_today)
elif selected_date_label == "Upcoming":
    date_display = "Next 7 Days"
else:
    date_display = _format_date(picked_date) if picked_date else ""

with hdr_title:
    st.markdown(
        f'<div class="page-header">'
        f"<h2>Predictions</h2>"
        f'<span style="color:#9CA3AF;font-size:0.85rem;">{date_display}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

with hdr_fresh:
    st.markdown(
        f'<div style="text-align:right;padding-top:0.5rem;">'
        f'<span class="{fresh_cls}">{fresh_text}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Helper: Build game card HTML for sidebar ────────────────────────────────
def _build_game_card(game: dict, is_selected: bool) -> str:
    """Build sidebar game card HTML."""
    home = game.get("HOME_TEAM_NAME", "")
    away = game.get("VISITOR_TEAM_NAME", "")
    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)

    period = int(game.get("PERIOD") or 0)
    status = game.get("STATUS") or ""
    is_live = period > 0 and status != "Final"
    is_final = status == "Final"

    # Scores for live and final games
    if is_live or is_final:
        home_score = int(game.get("HOME_TEAM_SCORE") or 0)
        away_score = int(game.get("VISITOR_TEAM_SCORE") or 0)
        # Add loser class for final games
        away_loser = " loser" if is_final and away_score < home_score else ""
        home_loser = " loser" if is_final and home_score < away_score else ""
        score_html = f'<span class="pred-score{away_loser}">{away_score}</span>'
        home_score_html = f'<span class="pred-score{home_loser}">{home_score}</span>'
    else:
        score_html = ""
        home_score_html = ""

    # Build market lines for all three markets
    spread_line = game.get("SPREAD_HOME_LINE")
    spread_rating = int(game.get("SPREAD_HOME_RATING") or 0)
    ml_price = game.get("ML_HOME_PRICE")
    ml_rating = int(game.get("ML_HOME_RATING") or 0)
    total_line = game.get("TOTAL_LINE")
    total_rating = int(game.get("OVER_RATING") or 0)

    # Format each market
    spread_str = f"{float(spread_line):+g}" if spread_line else "—"
    ml_str = f"{int(ml_price):+d}" if ml_price else "—"
    total_str = f"O/U {float(total_line):g}" if total_line else "—"

    best_ev = game.get("BEST_EV")

    # Format best EV
    if best_ev is not None:
        ev_pct = float(best_ev) * 100
        ev_str = f"+{ev_pct:.1f}%" if ev_pct >= 0 else f"{ev_pct:.1f}%"
        ev_cls = "ev-positive" if ev_pct >= 0 else "ev-negative"
    else:
        ev_str = ""
        ev_cls = ""

    # Card classes
    card_cls = "odds-sidebar-card"
    if is_selected:
        card_cls += " selected"
    if is_live:
        card_cls += " live"

    # Status display
    if is_final:
        status_html = '<span class="odds-sidebar-status">FINAL</span>'
    elif is_live:
        status_html = f'<span class="odds-sidebar-status live">{status}</span>'
    else:
        game_dt = game.get("GAME_DATETIME")
        if game_dt:
            if isinstance(game_dt, str):
                utc_dt = datetime.fromisoformat(game_dt).replace(tzinfo=timezone.utc)
            else:
                utc_dt = game_dt.replace(tzinfo=timezone.utc)
            et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
            time_str = et_dt.strftime("%I:%M %p").lstrip("0")
            status_html = f'<span class="odds-sidebar-status">{time_str}</span>'
        else:
            status_html = '<span class="odds-sidebar-status">TBD</span>'

    # Build compact market cells with star indicators
    def _market_cell(label: str, value: str, rating: int) -> str:
        stars = "★" * rating if rating > 0 else ""
        star_cls = " has-value" if rating >= 4 else ""
        return f'<div class="pred-mkt{star_cls}"><span class="pred-mkt-lbl">{label}</span><span class="pred-mkt-val">{value}</span><span class="pred-mkt-stars">{stars}</span></div>'

    return (
        f'<div class="{card_cls}">'
        f'<div class="pred-compact-row">'
        f'<div class="pred-teams">'
        f'<div class="pred-team-row"><img src="{away_logo}" class="pred-team-logo">'
        f'<span class="pred-team-name">{away_abbr}</span>{score_html}</div>'
        f'<div class="pred-team-row"><img src="{home_logo}" class="pred-team-logo">'
        f'<span class="pred-team-name">{home_abbr}</span>{home_score_html}</div>'
        f'</div>'
        f'<div class="pred-mkts">'
        f'{_market_cell("SPR", spread_str, spread_rating)}'
        f'{_market_cell("ML", ml_str, ml_rating)}'
        f'{_market_cell("O/U", total_str.replace("O/U ", ""), total_rating)}'
        f'</div>'
        f'</div>'
        f'<div class="pred-compact-footer">{status_html}<span class="best-bet-ev {ev_cls}">{ev_str}</span></div>'
        f'</div>'
    )


# ── Session state ───────────────────────────────────────────────────────────
if "pred_selected_idx" not in st.session_state:
    st.session_state.pred_selected_idx = 0

# Reset selected index when mode or picked date changes
if "pred_last_mode" not in st.session_state:
    st.session_state.pred_last_mode = selected_date_label
if st.session_state.pred_last_mode != selected_date_label:
    st.session_state.pred_selected_idx = 0
    st.session_state.pred_last_mode = selected_date_label

if selected_date_label == "Pick a Date":
    if st.session_state.get("pred_last_picked_date") != picked_date:
        st.session_state.pred_selected_idx = 0
        st.session_state.pred_last_picked_date = picked_date


# ── Two-panel layout ────────────────────────────────────────────────────────
@st.fragment(run_every="60s")
def predictions_board():
    """Fetch and render two-panel predictions view. Re-runs every 60s."""
    df = get_predictions_all_markets(
        mode=query_mode, logical_today=_logical_today, picked_date=picked_date
    )

    if df.empty:
        if selected_date_label == "Today":
            empty_title = "No predictions for today"
            empty_sub = "Check the Upcoming tab for the next games"
        elif selected_date_label == "Upcoming":
            empty_title = "No upcoming predictions"
            empty_sub = "Predictions are generated when odds data is available"
        else:
            empty_title = f"No predictions for {_format_date(picked_date)}"
            empty_sub = "Try selecting a date with scheduled games"
        st.markdown(
            '<div class="empty-state">'
            f"<h3>{empty_title}</h3>"
            f"<p>{empty_sub}</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Categorize into live, upcoming, and final
    sections = categorize_predictions(df)
    live_df = sections["live"]
    upcoming_df = sections["upcoming"]
    final_df = sections["final"]

    if live_df.empty and upcoming_df.empty and final_df.empty:
        if selected_date_label == "Today":
            empty_title = "No games scheduled for today"
            empty_sub = "Check the Upcoming tab for the next games"
        elif selected_date_label == "Upcoming":
            empty_title = "No upcoming games"
            empty_sub = "No games with predictions in the next 7 days"
        else:
            empty_title = f"No games for {_format_date(picked_date)}"
            empty_sub = "Try selecting a different date"
        st.markdown(
            '<div class="empty-state">'
            f"<h3>{empty_title}</h3>"
            f"<p>{empty_sub}</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Combine for game list (upcoming first, then live, then final)
    all_games = pd.concat([upcoming_df, live_df, final_df], ignore_index=True)

    # Clamp index to valid range
    if st.session_state.pred_selected_idx >= len(all_games):
        st.session_state.pred_selected_idx = 0

    # Two-panel layout: game list (left) | detail (right)
    col_list, col_detail = st.columns([1, 2.5])

    with col_list:
        # Scrollable container like Odds page
        with st.container(height=700):
            # Upcoming games section (first), grouped by date
            if not upcoming_df.empty:
                st.markdown(
                    '<div class="section-header" style="margin-top:0;">UPCOMING</div>',
                    unsafe_allow_html=True,
                )
                upcoming_idx = 0
                for game_date, date_group in upcoming_df.groupby("GAME_DATE", sort=True):
                    # Show date sub-header for future dates (skip for today)
                    if game_date != _logical_today:
                        st.markdown(
                            f'<div style="color:#9CA3AF;font-size:0.75rem;font-weight:600;'
                            f'text-transform:uppercase;letter-spacing:0.05em;'
                            f'padding:0.5rem 0.75rem 0.25rem;margin-top:0.5rem;">'
                            f'{_format_date(game_date)}</div>',
                            unsafe_allow_html=True,
                        )
                    for j in range(len(date_group)):
                        game = date_group.iloc[j].to_dict()
                        global_idx = upcoming_idx
                        is_selected = st.session_state.pred_selected_idx == global_idx
                        card_html = _build_game_card(game, is_selected)
                        st.markdown(card_html, unsafe_allow_html=True)
                        if st.button(
                            "●" if is_selected else "▶",
                            key=f"pred_upcoming_{upcoming_idx}",
                            width="stretch",
                        ):
                            if not is_selected:
                                st.session_state.pred_selected_idx = global_idx
                                st.rerun()
                        upcoming_idx += 1

            # Track upcoming count for global index offset
            num_upcoming = len(upcoming_df)

            # Live games section
            if not live_df.empty:
                header_style = "margin-top:0;" if upcoming_df.empty else "margin-top:1rem;"
                st.markdown(
                    f'<div class="section-header live" style="{header_style}">LIVE</div>',
                    unsafe_allow_html=True,
                )
                for i in range(len(live_df)):
                    game = live_df.iloc[i].to_dict()
                    global_idx = num_upcoming + i
                    is_selected = st.session_state.pred_selected_idx == global_idx
                    card_html = _build_game_card(game, is_selected)
                    st.markdown(card_html, unsafe_allow_html=True)
                    if st.button(
                        "●" if is_selected else "▶",
                        key=f"pred_live_{i}",
                        width="stretch",
                    ):
                        if not is_selected:
                            st.session_state.pred_selected_idx = global_idx
                            st.rerun()

            # Final games section
            if not final_df.empty:
                header_style = "margin-top:0;" if (upcoming_df.empty and live_df.empty) else "margin-top:1rem;"
                st.markdown(
                    f'<div class="section-header" style="{header_style}">FINAL</div>',
                    unsafe_allow_html=True,
                )
                for i in range(len(final_df)):
                    game = final_df.iloc[i].to_dict()
                    global_idx = num_upcoming + len(live_df) + i
                    is_selected = st.session_state.pred_selected_idx == global_idx
                    card_html = _build_game_card(game, is_selected)
                    st.markdown(card_html, unsafe_allow_html=True)
                    if st.button(
                        "●" if is_selected else "▶",
                        key=f"pred_final_{i}",
                        width="stretch",
                    ):
                        if not is_selected:
                            st.session_state.pred_selected_idx = global_idx
                            st.rerun()

    with col_detail:
        # Best bets strip above detail panel
        best_bets_df = get_best_bets(
            mode=query_mode, logical_today=_logical_today, picked_date=picked_date
        )
        if not best_bets_df.empty:
            st.html(render_best_bets_strip(best_bets_df))

        # Get selected game
        selected_game = all_games.iloc[st.session_state.pred_selected_idx].to_dict()

        # Game header
        home = selected_game.get("HOME_TEAM_NAME", "")
        away = selected_game.get("VISITOR_TEAM_NAME", "")
        home_abbr = get_team_abbrev(home)
        away_abbr = get_team_abbrev(away)
        home_logo = get_logo_url(home, 500)
        away_logo = get_logo_url(away, 500)

        period = int(selected_game.get("PERIOD") or 0)
        status = selected_game.get("STATUS") or ""
        is_live = period > 0 and status != "Final"
        is_final = status == "Final"

        if is_live or is_final:
            home_score = int(selected_game.get("HOME_TEAM_SCORE") or 0)
            away_score = int(selected_game.get("VISITOR_TEAM_SCORE") or 0)
            header_html = (
                '<div class="odds-game-header">'
                f'<div class="odds-game-header-team">'
                f'<img src="{away_logo}">'
                f'<span class="odds-game-header-name">{away_abbr}</span>'
                f'<span class="odds-game-header-score">{away_score}</span>'
                '</div>'
                '<span class="odds-game-header-vs">-</span>'
                '<div class="odds-game-header-team">'
                f'<span class="odds-game-header-score">{home_score}</span>'
                f'<span class="odds-game-header-name">{home_abbr}</span>'
                f'<img src="{home_logo}">'
                '</div>'
                '</div>'
            )
        else:
            header_html = (
                '<div class="odds-game-header">'
                f'<div class="odds-game-header-team">'
                f'<img src="{away_logo}">'
                f'<span class="odds-game-header-name">{away}</span>'
                '</div>'
                '<span class="odds-game-header-vs">@</span>'
                '<div class="odds-game-header-team">'
                f'<span class="odds-game-header-name">{home}</span>'
                f'<img src="{home_logo}">'
                '</div>'
                '</div>'
            )

        st.markdown(header_html, unsafe_allow_html=True)

        # Render full prediction analysis showing all markets
        render_all_markets_prediction(selected_game)


predictions_board()
