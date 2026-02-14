"""Odds page — Live odds comparison, line movement charts, and bookmaker analysis."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from styles.theme import inject_css
from queries.odds import (
    get_odds_for_date,
    get_odds_movement,
    get_odds_games,
    get_game_statuses,
    get_odds_freshness,
    get_opening_odds,
    fmt_price,
    fmt_line,
    fmt_prob,
    _is_missing,
)
from components.odds_charts import (
    build_line_movement_chart,
    build_bookmaker_comparison_wide,
    build_probability_bar,
    build_summary_card,
    build_movement_card,
    get_available_bookmakers,
    BOOKMAKER_DISPLAY,
    BOOKMAKER_SHORT,
)
from data.teams import get_logo_url, get_team_abbrev


# ── Custom CSS ────────────────────────────────────────────────────────────────
st.html(inject_css())

# 6am CST rollover — same logic as games.py / predictions.py
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


# ── Freshness ────────────────────────────────────────────────────────────────
freshness = get_odds_freshness()
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
    elif delta_secs < 600:
        fresh_text = f"Updated {int(delta_secs / 60)}m ago"
        fresh_cls = "freshness"
    else:
        fresh_text = f"Updated {int(delta_secs / 60)}m ago"
        fresh_cls = "freshness stale"
else:
    fresh_text = "No data"
    fresh_cls = "freshness stale"

# ── Header row ────────────────────────────────────────────────────────────────
hdr_title, hdr_date, hdr_market, hdr_fresh = st.columns([2, 1.2, 2, 1.5])

with hdr_date:
    selected_label = st.segmented_control(
        "Date",
        options=["Today", "Yesterday"],
        default="Today",
        label_visibility="collapsed",
    )

# Derive date directly from _logical_today (never falls back to DB)
if selected_label == "Yesterday":
    selected_date = _logical_today - timedelta(days=1)
else:
    selected_date = _logical_today
date_display = _format_date(selected_date)

with hdr_title:
    st.markdown(
        f'<div class="page-header">'
        f"<h2>Odds</h2>"
        f'<span style="color:#9CA3AF;font-size:0.85rem;">{date_display}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

with hdr_market:
    MARKET_OPTIONS = ["Spreads", "H2H", "Totals"]
    MARKET_MAP = {"Spreads": "spreads", "H2H": "h2h", "Totals": "totals"}
    market_label = st.segmented_control(
        "Market",
        options=MARKET_OPTIONS,
        default="Spreads",
        label_visibility="collapsed",
    )
    market_key = MARKET_MAP.get(market_label, "spreads")

with hdr_fresh:
    st.markdown(
        f'<div style="text-align:right;padding-top:0.5rem;">'
        f'<span class="{fresh_cls}">{fresh_text}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


# ── Session state ─────────────────────────────────────────────────────────────
if "odds_selected_event" not in st.session_state:
    st.session_state["odds_selected_event"] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════════


def _format_tipoff_from_row(game_row) -> str:
    """Format tip-off time from a DataFrame row."""
    commence = game_row.get("COMMENCE_TIME_UTC")
    if commence is None:
        return ""
    try:
        dt = pd.Timestamp(commence)
        if dt.tzinfo is None:
            dt = dt.tz_localize("UTC")
        et = dt.astimezone(ZoneInfo("America/New_York"))
        hour = et.strftime("%I").lstrip("0")
        return f"{hour}:{et.strftime('%M %p')} ET"
    except Exception:
        return ""


def _clean_clock(period: int, clock: str) -> str:
    """Build a clean clock display like 'Q3 7:34', avoiding duplication.

    The BDL API sometimes includes quarter info in the clock field
    (e.g. 'Q3 7:34' or 'END Q1'), causing 'Q3 Q3 7:34' if we also
    prefix with Q{period}. This strips redundant quarter prefixes.
    """
    c = str(clock).strip()
    if not c:
        return f"Q{period}"
    # If clock already starts with Q/q or includes END, use it as-is
    if c.upper().startswith("Q") or c.upper().startswith("END"):
        return c
    return f"Q{period} {c}"


def _game_status_text(game_row, status_map: dict) -> str:
    """Get a short status string for a game."""
    home = game_row["HOME_TEAM"]
    info = status_map.get(home)
    if not info:
        return _format_tipoff_from_row(game_row)
    status = info.get("STATUS", "")
    period = int(info.get("PERIOD", 0) or 0)
    clock = info.get("CLOCK", "") or ""
    h_score = int(info.get("HOME_TEAM_SCORE", 0) or 0)
    v_score = int(info.get("VISITOR_TEAM_SCORE", 0) or 0)
    if status == "Final":
        return f"FINAL {v_score}-{h_score}"
    elif period > 0:
        clock_display = _clean_clock(period, clock)
        return f"{clock_display} {v_score}-{h_score}"
    return _format_tipoff_from_row(game_row)


def _is_live(status_map: dict, home_team: str) -> bool:
    """Check if a game is currently live."""
    info = status_map.get(home_team)
    if not info:
        return False
    period = int(info.get("PERIOD", 0) or 0)
    status = info.get("STATUS", "")
    return period > 0 and status != "Final"


def _is_final(status_map: dict, home_team: str) -> bool:
    """Check if a game is final."""
    info = status_map.get(home_team)
    if not info:
        return False
    return info.get("STATUS", "") == "Final"


def _get_consensus_line(odds_df, event_id, market_key, home_team):
    """Get consensus line string for a game/market."""
    game_mkt = odds_df[
        (odds_df["EVENT_ID"] == event_id) & (odds_df["MARKET_KEY"] == market_key)
    ]
    if game_mkt.empty:
        return ""
    if market_key == "totals":
        side_df = game_mkt[game_mkt["SIDE"] == "Over"]
    else:
        side_df = game_mkt[game_mkt["SIDE"] == home_team]
    if side_df.empty:
        return ""
    r = side_df.iloc[0]
    if market_key == "h2h":
        return fmt_price(r.get("CONSENSUS_PRICE"))
    return fmt_line(r.get("CONSENSUS_LINE"))


def _get_best_odds(odds_df, event_id, market_key, side):
    """Get best (highest) price for a side and which bookmaker offers it.

    Returns (price_str, bookmaker_short) or ("", "").
    """
    game_mkt = odds_df[
        (odds_df["EVENT_ID"] == event_id)
        & (odds_df["MARKET_KEY"] == market_key)
        & (odds_df["SIDE"] == side)
    ]
    if game_mkt.empty:
        return "", ""
    best_idx = game_mkt["OUTCOME_PRICE"].idxmax()
    best_row = game_mkt.loc[best_idx]
    price = best_row["OUTCOME_PRICE"]
    bk = best_row["BOOKMAKER_KEY"]
    bk_short = BOOKMAKER_SHORT.get(bk, bk[:3].upper())
    if market_key == "h2h":
        return fmt_price(price), bk_short
    point = best_row.get("OUTCOME_POINT")
    if not _is_missing(point):
        return f"{fmt_line(point)} ({fmt_price(price)})", bk_short
    return fmt_price(price), bk_short


def _parse_clock_seconds(clock_str) -> float:
    """Parse game clock string to total seconds remaining."""
    if not clock_str:
        return 720.0
    try:
        parts = str(clock_str).strip().split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return 720.0
    except (ValueError, IndexError):
        return 720.0


def _game_sort_key(game_row, status_map):
    """Sort key: live games closest to ending first, then final, then upcoming."""
    home = game_row["HOME_TEAM"]
    info = status_map.get(home, {})
    status = info.get("STATUS", "")
    period = int(info.get("PERIOD", 0) or 0)
    clock = info.get("CLOCK", "") or ""

    if period > 0 and status != "Final":
        # Live: higher period + less clock = closer to ending
        clock_secs = _parse_clock_seconds(clock)
        return (0, -period, clock_secs)
    elif status == "Final":
        return (1, 0, 0)
    else:
        ct = str(game_row.get("COMMENCE_TIME_UTC", ""))
        return (2, 0, ct)


def _build_sidebar_card(game_row, status_map, odds_df, mkt_key, is_selected):
    """Build HTML for a game card in the left sidebar."""
    home = game_row["HOME_TEAM"]
    away = game_row["AWAY_TEAM"]
    eid = game_row["EVENT_ID"]
    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)

    info = status_map.get(home, {})
    status = info.get("STATUS", "")
    period = int(info.get("PERIOD", 0) or 0)
    h_score = int(info.get("HOME_TEAM_SCORE", 0) or 0)
    v_score = int(info.get("VISITOR_TEAM_SCORE", 0) or 0)
    clock = info.get("CLOCK", "") or ""

    live = period > 0 and status != "Final"
    final = status == "Final"

    sel_cls = " selected" if is_selected else ""
    live_cls = " live" if live else ""

    # Scores
    if live or final:
        v_loser = " loser" if final and v_score < h_score else ""
        h_loser = " loser" if final and h_score < v_score else ""
        away_score = f'<span class="odds-sidebar-score{v_loser}">{v_score}</span>'
        home_score = f'<span class="odds-sidebar-score{h_loser}">{h_score}</span>'
    else:
        away_score = ""
        home_score = ""

    # Status
    if final:
        status_html = "FINAL"
        status_cls = ""
    elif live:
        clock_display = _clean_clock(period, clock)
        status_html = f'<span class="live-dot"></span>{clock_display}'
        status_cls = " live"
    else:
        status_html = _format_tipoff_from_row(game_row)
        status_cls = ""

    # Best odds for each side
    if mkt_key == "totals":
        away_best, away_bk = _get_best_odds(odds_df, eid, mkt_key, "Over")
        home_best, home_bk = _get_best_odds(odds_df, eid, mkt_key, "Under")
    else:
        away_best, away_bk = _get_best_odds(odds_df, eid, mkt_key, away)
        home_best, home_bk = _get_best_odds(odds_df, eid, mkt_key, home)

    away_odds_html = (
        f'<span class="odds-sidebar-best">{away_best}'
        f'<span class="odds-sidebar-bk">{away_bk}</span></span>'
        if away_best else ""
    )
    home_odds_html = (
        f'<span class="odds-sidebar-best">{home_best}'
        f'<span class="odds-sidebar-bk">{home_bk}</span></span>'
        if home_best else ""
    )

    return (
        f'<div class="odds-sidebar-card{sel_cls}{live_cls}">'
        f'<div class="odds-sidebar-row">'
        f'<img class="odds-sidebar-logo" src="{away_logo}" alt="">'
        f'<span class="odds-sidebar-name">{away_abbr}</span>'
        f'{away_odds_html}'
        f'{away_score}'
        f'</div>'
        f'<div class="odds-sidebar-row">'
        f'<img class="odds-sidebar-logo" src="{home_logo}" alt="">'
        f'<span class="odds-sidebar-name">{home_abbr}</span>'
        f'{home_odds_html}'
        f'{home_score}'
        f'</div>'
        f'<div class="odds-sidebar-footer">'
        f'<span class="odds-sidebar-status{status_cls}">{status_html}</span>'
        f'</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main auto-refresh fragment
# ═══════════════════════════════════════════════════════════════════════════════


@st.fragment(run_every="60s")
def odds_board():
    """Main odds page content. Auto-refreshes every 60 seconds."""
    if selected_date is None:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No odds data available</h3>"
            "<p>Odds appear during game hours (11 AM \u2013 2 AM ET)</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Fetch data
    odds_df = get_odds_for_date(selected_date)
    games_df = get_odds_games(selected_date)
    statuses_df = get_game_statuses(selected_date)

    if games_df.empty:
        st.markdown(
            '<div class="empty-state">'
            "<h3>No odds data for this date</h3>"
            "<p>Odds are captured every 5 minutes during game hours.</p>"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    # Deduplicate
    games_df = games_df.drop_duplicates(subset=["EVENT_ID"])

    # Build status lookup: home_team_name -> status row
    status_map = {}
    if not statuses_df.empty:
        for _, row in statuses_df.iterrows():
            status_map[row["HOME_TEAM_NAME"]] = row.to_dict()

    # Sort games: live games closest to ending first, then final, then upcoming
    game_list = list(games_df.iterrows())
    game_list.sort(key=lambda x: _game_sort_key(x[1], status_map))
    event_ids = [g["EVENT_ID"] for _, g in game_list]

    # Default to first game (closest to ending)
    current_sel = st.session_state.get("odds_selected_event")
    if current_sel not in event_ids:
        current_sel = event_ids[0]
        st.session_state["odds_selected_event"] = current_sel

    # ── Two-panel layout: game list (left) | detail (right) ────────────
    left_col, right_col = st.columns([1, 2.5])

    with left_col:
        with st.container(height=750):
            for _, game in game_list:
                eid = game["EVENT_ID"]
                is_sel = eid == current_sel
                card_html = _build_sidebar_card(
                    game, status_map, odds_df, market_key, is_sel,
                )
                st.markdown(card_html, unsafe_allow_html=True)
                if st.button(
                    "\u25CF" if is_sel else "\u25B6",
                    key=f"game_{eid}",
                    width="stretch",
                ):
                    if not is_sel:
                        st.session_state["odds_selected_event"] = eid
                        st.rerun()

    with right_col:
        _render_game_detail(current_sel, odds_df, games_df, status_map)

    # ── Bookmaker comparison — full width below both panels ──────────
    sel_odds = odds_df[odds_df["EVENT_ID"] == current_sel]
    if not sel_odds.empty:
        sel_row = sel_odds.iloc[0]
        st.markdown(
            '<div class="section-header">BOOKMAKER COMPARISON</div>',
            unsafe_allow_html=True,
        )
        comparison_html = build_bookmaker_comparison_wide(
            odds_df, current_sel, market_key,
            sel_row["HOME_TEAM"], sel_row["AWAY_TEAM"],
        )
        comparison_html = "\n".join(
            line.lstrip() for line in comparison_html.splitlines()
        )
        st.markdown(comparison_html, unsafe_allow_html=True)


def _render_game_detail(
    event_id: str,
    odds_df: pd.DataFrame,
    games_df: pd.DataFrame,
    status_map: dict,
):
    """Render full odds analysis for the selected game."""
    game_odds = odds_df[odds_df["EVENT_ID"] == event_id]
    if game_odds.empty:
        st.info("No odds data for this game.")
        return

    row0 = game_odds.iloc[0]
    home = row0["HOME_TEAM"]
    away = row0["AWAY_TEAM"]
    commence_time = row0.get("COMMENCE_TIME_UTC")
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)
    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)

    # Game header with scores if live/final
    info = status_map.get(home, {})
    period = int(info.get("PERIOD", 0) or 0)
    h_score = int(info.get("HOME_TEAM_SCORE", 0) or 0)
    v_score = int(info.get("VISITOR_TEAM_SCORE", 0) or 0)

    if period > 0:
        score_html = (
            f'<span class="odds-game-header-score">{v_score}</span>'
            f'<span class="odds-game-header-vs">-</span>'
            f'<span class="odds-game-header-score">{h_score}</span>'
        )
    else:
        score_html = '<span class="odds-game-header-vs">vs</span>'

    header_html = (
        f'<div class="odds-game-header">'
        f'<div class="odds-game-header-team">'
        f'<img src="{away_logo}" alt="">'
        f'<span class="odds-game-header-name">{away_abbr}</span>'
        f'</div>'
        f'{score_html}'
        f'<div class="odds-game-header-team">'
        f'<span class="odds-game-header-name">{home_abbr}</span>'
        f'<img src="{home_logo}" alt="">'
        f'</div>'
        f'</div>'
    )
    st.markdown(header_html, unsafe_allow_html=True)

    # ── Summary cards ────────────────────────────────────────────────────
    market_odds = game_odds[game_odds["MARKET_KEY"] == market_key]

    if market_key == "totals":
        home_side = market_odds[market_odds["SIDE"] == "Over"]
        away_side = market_odds[market_odds["SIDE"] == "Under"]
    else:
        home_side = market_odds[market_odds["SIDE"] == home]
        away_side = market_odds[market_odds["SIDE"] == away]

    game_is_final = _is_final(status_map, home)

    if not home_side.empty and not away_side.empty:
        h = home_side.iloc[0]
        a = away_side.iloc[0]
        c_line = h.get("CONSENSUS_LINE")
        c_price = h.get("CONSENSUS_PRICE")
        h_prob = h.get("CONSENSUS_IMPLIED_PROB")
        a_prob = a.get("CONSENSUS_IMPLIED_PROB")

        # Try to get opening line
        opening_df = get_opening_odds(selected_date)
        opening_val = None
        opening_price = None
        if not opening_df.empty:
            open_game = opening_df[opening_df["EVENT_ID"] == event_id]
            if not open_game.empty:
                if market_key == "totals":
                    open_side = open_game[
                        (open_game["MARKET_KEY"] == market_key)
                        & (open_game["SIDE"] == "Over")
                    ]
                else:
                    open_side = open_game[
                        (open_game["MARKET_KEY"] == market_key)
                        & (open_game["SIDE"] == home)
                    ]
                if not open_side.empty:
                    opening_price = open_side["OUTCOME_PRICE"].median()
                    if market_key == "h2h":
                        opening_val = opening_price
                    else:
                        opening_val = open_side["OUTCOME_POINT"].median()

        # Current value for movement
        if market_key == "h2h":
            current_val = c_price
            current_display = fmt_price(c_price)
            opening_display = fmt_price(opening_val) if not _is_missing(opening_val) else "N/A"
        else:
            current_val = c_line
            current_display = fmt_line(c_line)
            opening_display = fmt_line(opening_val) if not _is_missing(opening_val) else "N/A"

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            open_sub_parts = []
            if market_key != "h2h" and not _is_missing(opening_price):
                open_sub_parts.append(fmt_price(opening_price))
            if not _is_missing(opening_val):
                open_sub_parts.append(fmt_prob(
                    float(abs(opening_price)) / (abs(opening_price) + 100.0)
                    if not _is_missing(opening_price) and float(opening_price) < 0
                    else (100.0 / (float(opening_price) + 100.0)
                          if not _is_missing(opening_price) and float(opening_price) > 0
                          else None)
                ))
            open_sub = " · ".join(p for p in open_sub_parts if p and p != "N/A")
            st.markdown(
                build_summary_card("OPENING LINE", opening_display, open_sub),
                unsafe_allow_html=True,
            )
        with c2:
            line_label = "CLOSING LINE" if game_is_final else "CURRENT LINE"
            cur_sub = ""
            if market_key != "h2h":
                cur_sub = fmt_price(c_price)
            st.markdown(
                build_summary_card(line_label, current_display, cur_sub),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                build_movement_card(opening_val, current_val, market_key),
                unsafe_allow_html=True,
            )
        with c4:
            if not _is_missing(h_prob) and not _is_missing(a_prob):
                if market_key == "totals":
                    prob_html = build_probability_bar(
                        "Over", "Under",
                        float(h_prob), float(a_prob),
                    )
                else:
                    prob_html = build_probability_bar(
                        home, away,
                        float(h_prob), float(a_prob),
                    )
                st.markdown(prob_html, unsafe_allow_html=True)
            else:
                st.markdown(
                    build_summary_card("IMPLIED PROBABILITY", "N/A"),
                    unsafe_allow_html=True,
                )

    # ── Line movement chart ──────────────────────────────────────────────
    st.markdown(
        '<div class="section-header">LINE MOVEMENT</div>',
        unsafe_allow_html=True,
    )

    movement_df = get_odds_movement(event_id)

    # Controls: side toggle | bookmaker selector | probability toggle
    ctrl_side, ctrl_book, ctrl_prob = st.columns([3, 2, 1])

    with ctrl_side:
        if market_key == "totals":
            side_options = ["Over", "Under"]
            side_choice = st.segmented_control(
                "Side",
                options=side_options,
                default="Over",
                label_visibility="collapsed",
                key="odds_side_toggle",
            )
            chart_side = side_choice or "Over"
        else:
            side_options = [away_abbr, home_abbr]
            side_choice = st.segmented_control(
                "Side",
                options=side_options,
                default=home_abbr,
                label_visibility="collapsed",
                key="odds_side_toggle",
            )
            chart_side = home if side_choice == home_abbr else away

    with ctrl_book:
        # Build bookmaker options: Consensus + available books
        book_options = ["consensus"]
        if not movement_df.empty:
            book_options += get_available_bookmakers(movement_df)
        book_labels = {
            "consensus": "Consensus",
            **{bk: BOOKMAKER_DISPLAY.get(bk, bk.title()) for bk in book_options[1:]},
        }
        selected_source = st.selectbox(
            "Source",
            options=book_options,
            format_func=lambda bk: book_labels.get(bk, bk),
            index=0,
            label_visibility="collapsed",
            key="odds_book_select",
        )

    with ctrl_prob:
        show_prob = st.toggle("Prob %", value=False, key="odds_prob_toggle")

    if movement_df.empty:
        st.caption(
            "No line movement history yet. "
            "Snapshots are captured every 5 minutes during game hours."
        )
    else:
        fig = build_line_movement_chart(
            movement_df,
            market_key,
            chart_side,
            commence_time_utc=commence_time,
            show_implied_prob=show_prob,
            selected_source=selected_source,
            is_final=game_is_final,
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    # Bookmaker comparison is rendered in odds_board() below both panels


# ── Run the board ─────────────────────────────────────────────────────────────
odds_board()
