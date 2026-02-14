"""Grades page — Post-game team and player performance grades."""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from styles.theme import inject_css
from queries.grades import (
    get_available_grade_dates,
    get_team_grades,
    get_player_grades,
)
from data.teams import get_team_abbrev, get_logo_url

# ── CSS ──────────────────────────────────────────────────────────────────────
st.html(inject_css())

# ── Grade helpers ────────────────────────────────────────────────────────────

GRADE_CSS_CLASS = {
    "A+": "grade-a-plus",
    "A": "grade-a",
    "B": "grade-b",
    "C": "grade-c",
    "D": "grade-d",
    "F": "grade-f",
}


def _grade_cls(grade: str) -> str:
    return GRADE_CSS_CLASS.get(grade, "grade-c")


def _delta_cls(val) -> str:
    if pd.isna(val):
        return "neutral"
    if val > 0.5:
        return "positive"
    if val < -0.5:
        return "negative"
    return "neutral"


def _fmt_delta(val, decimals: int = 1) -> str:
    if pd.isna(val):
        return "-"
    if val > 0:
        return f"+{val:.{decimals}f}"
    return f"{val:.{decimals}f}"


def _fmt_pct_delta(val) -> str:
    if pd.isna(val):
        return "-"
    pct = val * 100
    if pct > 0:
        return f"+{pct:.1f}%"
    return f"{pct:.1f}%"


def _fmt_pct(val) -> str:
    if pd.isna(val):
        return "-"
    return f"{val * 100:.1f}%"


def _safe_int(val) -> str:
    if pd.isna(val):
        return "-"
    return str(int(val))


def _spread_cls(result) -> str:
    if pd.isna(result) or result is None:
        return ""
    r = str(result).upper()
    if r == "COVERED":
        return "covered"
    if r in ("MISSED", "NOT COVERED"):
        return "missed"
    if r == "PUSH":
        return "push"
    return ""


# ── Date logic ───────────────────────────────────────────────────────────────

_CST = ZoneInfo("America/Chicago")
_now_cst = datetime.now(_CST)
_logical_today = (
    (_now_cst - timedelta(days=1)).date() if _now_cst.hour < 6 else _now_cst.date()
)

available_dates = get_available_grade_dates()


def _to_date(d):
    if isinstance(d, str):
        return datetime.fromisoformat(d).date()
    return pd.Timestamp(d).date()


def _format_date(d) -> str:
    if d is None:
        return ""
    if isinstance(d, str):
        d = datetime.fromisoformat(d)
    try:
        return d.strftime("%A, %B %-d, %Y")
    except ValueError:
        return d.strftime("%A, %B %d, %Y").replace(" 0", " ")


today_raw = None
yesterday_raw = None
for d in available_dates:
    dd = _to_date(d)
    if dd == _logical_today:
        today_raw = d
    elif dd == _logical_today - timedelta(days=1):
        yesterday_raw = d

seg_options = []
seg_map = {}
if today_raw is not None:
    seg_options.append("Today")
    seg_map["Today"] = today_raw
if yesterday_raw is not None:
    seg_options.append("Yesterday")
    seg_map["Yesterday"] = yesterday_raw
if not seg_options and available_dates:
    seg_options.append("Latest")
    seg_map["Latest"] = available_dates[0]

# ── Header ───────────────────────────────────────────────────────────────────
hdr_title, hdr_date, hdr_picker = st.columns([3, 2, 2])

with hdr_date:
    if seg_options:
        selected_label = st.segmented_control(
            "Date",
            options=seg_options + ["Pick date"],
            default=seg_options[0],
            label_visibility="collapsed",
        )
    else:
        selected_label = "Pick date"

with hdr_picker:
    if selected_label == "Pick date":
        date_options = [_to_date(d) for d in available_dates] if available_dates else []
        default_val = date_options[0] if date_options else _logical_today
        picked_date = st.date_input(
            "Game date",
            value=default_val,
            min_value=date_options[-1] if date_options else None,
            max_value=date_options[0] if date_options else None,
            label_visibility="collapsed",
        )
        selected_date = picked_date
    else:
        selected_date = (
            _to_date(seg_map.get(selected_label, available_dates[0]))
            if available_dates
            else None
        )
        st.write("")

date_display = _format_date(selected_date) if selected_date else ""

with hdr_title:
    st.markdown(
        f'<div class="page-header">'
        f"<h2>Performance Grades</h2>"
        f'<span style="color:#9CA3AF;font-size:0.85rem;">{date_display}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

if selected_date is None:
    st.markdown(
        '<div class="empty-state">'
        "<h3>No grades data available</h3>"
        "<p>Grades are generated after games are finalized.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Load data ────────────────────────────────────────────────────────────────
team_grades = get_team_grades(selected_date)
player_grades = get_player_grades(selected_date)

if team_grades.empty:
    st.markdown(
        '<div class="empty-state">'
        "<h3>No grades for this date</h3>"
        "<p>Try selecting a date with completed NBA games.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()


# ── Build game list ──────────────────────────────────────────────────────────

def _get_team_row(game_id, is_home: bool):
    mask = (team_grades["GAME_ID"] == game_id) & (team_grades["IS_HOME"] == is_home)
    rows = team_grades[mask]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


game_ids = list(team_grades["GAME_ID"].unique())

game_labels = []
game_label_to_id = {}
for gid in game_ids:
    home = _get_team_row(gid, True)
    away = _get_team_row(gid, False)
    if home and away:
        h_abbr = get_team_abbrev(home["TEAM_NAME"])
        a_abbr = get_team_abbrev(away["TEAM_NAME"])
        label = f"{a_abbr} @ {h_abbr}"
    else:
        label = f"Game {gid}"
    game_labels.append(label)
    game_label_to_id[label] = gid

# ── Game selector ────────────────────────────────────────────────────────────
if len(game_labels) > 1:
    selected_game_label = st.segmented_control(
        "Game",
        options=game_labels,
        default=game_labels[0],
        label_visibility="collapsed",
    )
else:
    selected_game_label = game_labels[0] if game_labels else None

if selected_game_label is None:
    st.stop()

selected_game_id = game_label_to_id[selected_game_label]
home = _get_team_row(selected_game_id, True)
away = _get_team_row(selected_game_id, False)

if home is None or away is None:
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# Rendering helpers
# ══════════════════════════════════════════════════════════════════════════════

def _render_grade_badge(grade: str, size: str = "large") -> str:
    cls = _grade_cls(grade)
    if size == "large":
        return f'<span class="grade-badge {cls}">{grade}</span>'
    return f'<span class="grade-small-badge {cls}">{grade}</span>'


def _render_team_column(team: dict) -> str:
    """Render one team's grade column with a clean aligned stat table."""
    name = team.get("TEAM_NAME", "")
    abbrev = get_team_abbrev(name)
    logo = get_logo_url(name)
    pts = _safe_int(team.get("PTS"))
    spread_result = team.get("SPREAD_RESULT")
    spread_css = _spread_cls(spread_result)
    spread_text = str(spread_result).upper() if not pd.isna(spread_result) else ""

    overall = team.get("PERFORMANCE_GRADE", "C")
    off_grade = team.get("OFF_PERFORMANCE_GRADE", "C")
    def_grade = team.get("DEF_PERFORMANCE_GRADE", "C")

    # Build stat table rows
    stats = [
        ("PTS", team.get("PTS"), team.get("L10_AVG_PTS"), team.get("PTS_DELTA_L10"), False, False),
        ("OFF RTG", team.get("OFF_RATING"), team.get("L10_AVG_OFF_RATING"), team.get("OFF_RATING_DELTA_L10"), False, True),
        ("DEF RTG", team.get("DEF_RATING"), team.get("L10_AVG_DEF_RATING"), team.get("DEF_RATING_DELTA_L10"), True, True),
        ("REB", team.get("REB"), None, team.get("REB_DELTA_L10"), False, False),
        ("AST", team.get("AST"), None, team.get("AST_DELTA_L10"), False, False),
        ("FG%", team.get("FG_PCT"), None, team.get("FG_PCT_DELTA_L10"), False, True),
    ]

    rows_html = ""
    for label, actual, avg, delta, inverted, is_decimal in stats:
        if label == "FG%":
            actual_str = _fmt_pct(actual)
            avg_str = _fmt_pct(avg) if avg is not None and not pd.isna(avg) else "-"
            delta_str = _fmt_pct_delta(delta)
        elif is_decimal:
            actual_str = f"{actual:.1f}" if not pd.isna(actual) else "-"
            avg_str = f"{avg:.1f}" if avg is not None and not pd.isna(avg) else "-"
            delta_str = _fmt_delta(delta)
        else:
            actual_str = _safe_int(actual)
            avg_str = f"{avg:.1f}" if avg is not None and not pd.isna(avg) else "-"
            delta_str = _fmt_delta(delta)

        if inverted and not pd.isna(delta):
            d_cls = _delta_cls(-delta)
        else:
            d_cls = _delta_cls(delta) if not pd.isna(delta) else "neutral"

        rows_html += (
            f'<div class="grade-stat-row">'
            f'<span class="grade-stat-label">{label}</span>'
            f'<span class="grade-stat-actual">{actual_str}</span>'
            f'<span class="grade-stat-avg">{avg_str}</span>'
            f'<span class="grade-stat-delta {d_cls}">{delta_str}</span>'
            f'</div>'
        )

    spread_pill = ""
    if spread_text:
        spread_pill = f'<span class="grade-spread-pill {spread_css}">{spread_text}</span>'

    return (
        f'<div class="grade-team-col">'
        f'<div class="grade-team-header">'
        f'<img src="{logo}" alt="{abbrev}">'
        f'<span class="grade-team-header-name">{abbrev}</span>'
        f'<span class="grade-team-header-score">{pts}</span>'
        f'{spread_pill}'
        f'</div>'
        f'<div class="grade-overview">'
        f'{_render_grade_badge(overall)}'
        f'<div class="grade-sub-grades">'
        f'<div class="grade-sub-row">'
        f'<span class="grade-sub-label">OFF</span>'
        f'{_render_grade_badge(off_grade, "small")}'
        f'</div>'
        f'<div class="grade-sub-row">'
        f'<span class="grade-sub-label">DEF</span>'
        f'{_render_grade_badge(def_grade, "small")}'
        f'</div>'
        f'</div>'
        f'</div>'
        f'<div class="grade-stats">'
        f'<div class="grade-stat-col-hdr">'
        f'<span class="grade-stat-label">STAT</span>'
        f'<span class="grade-stat-actual">ACT</span>'
        f'<span class="grade-stat-avg">L10</span>'
        f'<span class="grade-stat-delta">+/-</span>'
        f'</div>'
        f'{rows_html}'
        f'</div>'
        f'</div>'
    )


def _build_takeaways(team: dict) -> list[dict]:
    """Build sorted list of key performance factors for a team.

    Returns list of dicts with stat, delta_str, desc, positive.
    Sorted by |delta| descending, top 4 returned.
    """
    factors = []

    # (col, stat_label, desc_template_good, desc_template_bad, inverted, is_pct)
    checks = [
        ("PTS_DELTA_L10", "Points", "{d} more than L10 avg", "{d} fewer than L10 avg", False, False),
        ("OFF_RATING_DELTA_L10", "Off Rating", "{d} pts/100 above avg", "{d} pts/100 below avg", False, False),
        ("DEF_RATING_DELTA_L10", "Def Rating", "{d} pts/100 tighter", "{d} pts/100 worse", True, False),
        ("REB_DELTA_L10", "Rebounds", "{d} more than avg", "{d} fewer than avg", False, False),
        ("AST_DELTA_L10", "Assists", "{d} more than avg", "{d} fewer than avg", False, False),
        ("TURNOVERS_DELTA_L10", "Turnovers", "{d} fewer than avg", "{d} more than avg", True, False),
        ("STL_DELTA_L10", "Steals", "{d} more than avg", "{d} fewer than avg", False, False),
        ("BLK_DELTA_L10", "Blocks", "{d} more than avg", "{d} fewer than avg", False, False),
        ("FG_PCT_DELTA_L10", "FG%", "{d} above avg", "{d} below avg", False, True),
        ("FG3_PCT_DELTA_L10", "3PT%", "{d} above avg", "{d} below avg", False, True),
    ]

    for col, stat_label, good_tpl, bad_tpl, inverted, is_pct in checks:
        val = team.get(col)
        if pd.isna(val) or val is None:
            continue

        abs_val = abs(val)
        if is_pct and abs_val < 0.005:
            continue
        if not is_pct and abs_val < 0.5:
            continue

        raw_positive = val > 0
        is_good = (not raw_positive) if inverted else raw_positive

        if is_pct:
            d_str = f"{abs(val * 100):.1f}%"
        else:
            d_str = f"{abs_val:.1f}"

        desc = good_tpl.format(d=d_str) if is_good else bad_tpl.format(d=d_str)
        pill_str = f"+{d_str}" if is_good else f"-{d_str}"

        factors.append({
            "stat": stat_label,
            "abs_delta": abs_val if not is_pct else abs_val * 100,
            "desc": desc,
            "pill": pill_str,
            "positive": is_good,
        })

    factors.sort(key=lambda f: f["abs_delta"], reverse=True)
    return factors[:4]


def _render_takeaway_panel(team: dict) -> str:
    """Render key takeaway items for one team."""
    name = team.get("TEAM_NAME", "")
    abbrev = get_team_abbrev(name)
    logo = get_logo_url(name)
    overall = team.get("PERFORMANCE_GRADE", "C")

    factors = _build_takeaways(team)

    items_html = ""
    for f in factors:
        if f["positive"]:
            row_cls = "tk-good"
            arrow_cls = "tk-up"
            arrow = "&#9650;"  # ▲
            pill_cls = "tk-good-pill"
        else:
            row_cls = "tk-bad"
            arrow_cls = "tk-down"
            arrow = "&#9660;"  # ▼
            pill_cls = "tk-bad-pill"

        items_html += (
            f'<div class="grade-takeaway-item {row_cls}">'
            f'<span class="grade-takeaway-arrow {arrow_cls}">{arrow}</span>'
            f'<div class="grade-takeaway-body">'
            f'<div class="grade-takeaway-stat">{f["stat"]}</div>'
            f'<div class="grade-takeaway-desc">{f["desc"]}</div>'
            f'</div>'
            f'<span class="grade-takeaway-pill {pill_cls}">{f["pill"]}</span>'
            f'</div>'
        )

    if not items_html:
        items_html = (
            '<div class="grade-takeaway-item">'
            '<div class="grade-takeaway-body">'
            '<div class="grade-takeaway-desc" style="color:#6B7280;">Average performance across the board</div>'
            '</div></div>'
        )

    return (
        f'<div class="grade-takeaway-team">'
        f'<img src="{logo}" alt="{abbrev}">'
        f'<span class="grade-takeaway-team-name">{abbrev}</span>'
        f'{_render_grade_badge(overall, "small")}'
        f'</div>'
        f'{items_html}'
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEAM GRADES + KEY TAKEAWAYS
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(
    '<div class="section-header">TEAM GRADES</div>',
    unsafe_allow_html=True,
)

# Matchup header
home_name = home.get("TEAM_NAME", "")
away_name = away.get("TEAM_NAME", "")
home_abbrev = get_team_abbrev(home_name)
away_abbrev = get_team_abbrev(away_name)
home_logo = get_logo_url(home_name)
away_logo = get_logo_url(away_name)
home_pts = _safe_int(home.get("PTS"))
away_pts = _safe_int(away.get("PTS"))

home_pts_int = int(home.get("PTS", 0)) if not pd.isna(home.get("PTS")) else 0
away_pts_int = int(away.get("PTS", 0)) if not pd.isna(away.get("PTS")) else 0
home_score_cls = "winner" if home_pts_int >= away_pts_int else "loser"
away_score_cls = "winner" if away_pts_int >= home_pts_int else "loser"

matchup_html = (
    f'<div class="grade-matchup">'
    f'<div class="grade-matchup-team">'
    f'<img class="grade-matchup-logo" src="{away_logo}" alt="{away_abbrev}">'
    f'<span class="grade-matchup-name">{away_abbrev}</span>'
    f'</div>'
    f'<span class="grade-matchup-score {away_score_cls}">{away_pts}</span>'
    f'<span class="grade-matchup-vs">@</span>'
    f'<span class="grade-matchup-score {home_score_cls}">{home_pts}</span>'
    f'<div class="grade-matchup-team">'
    f'<span class="grade-matchup-name">{home_abbrev}</span>'
    f'<img class="grade-matchup-logo" src="{home_logo}" alt="{home_abbrev}">'
    f'</div>'
    f'</div>'
)

# Render both panels in a single HTML flex row so they match height
card_html = (
    f'<div class="grade-card">'
    f'{matchup_html}'
    f'<div class="grade-cols">'
    f'{_render_team_column(away)}'
    f'<div class="grade-divider"></div>'
    f'{_render_team_column(home)}'
    f'</div>'
    f'</div>'
)

takeaway_html = (
    f'<div class="grade-takeaway-panel">'
    f'{_render_takeaway_panel(away)}'
    f'<div class="grade-takeaway-divider"></div>'
    f'{_render_takeaway_panel(home)}'
    f'</div>'
)

st.markdown(
    f'<div class="grade-row">'
    f'<div style="flex:3;min-width:0;">{card_html}</div>'
    f'<div style="flex:2;min-width:0;">{takeaway_html}</div>'
    f'</div>',
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# PLAYER GRADES — inline, two columns (away | home)
# ══════════════════════════════════════════════════════════════════════════════

def _render_player_table(game_id, is_home: bool) -> str:
    mask = (player_grades["GAME_ID"] == game_id) & (player_grades["IS_HOME"] == is_home)
    players = player_grades[mask].copy()

    if players.empty:
        return '<div class="stats-empty">No player data</div>'

    team_name = players.iloc[0]["TEAM_NAME"]
    abbrev = get_team_abbrev(team_name)
    logo = get_logo_url(team_name)

    html = (
        f'<div class="grade-player-team-hdr">'
        f'<img src="{logo}" alt="{abbrev}">'
        f'<span class="grade-player-team-hdr-name">{team_name}</span>'
        f'</div>'
    )

    html += (
        '<div class="grade-player-col-hdr">'
        '<span class="grade-player-name">PLAYER</span>'
        '<span class="grade-player-stat">MIN</span>'
        '<span class="grade-player-stat">PTS</span>'
        '<span class="grade-player-stat">REB</span>'
        '<span class="grade-player-stat">AST</span>'
        '<span class="grade-player-gs">GmSc</span>'
        '<span class="grade-player-delta">+/-</span>'
        '<span class="grade-player-grade">GRD</span>'
        '</div>'
    )

    for _, p in players.iterrows():
        name = p.get("PLAYER_NAME", "")
        mins = f"{p['MINUTES_PLAYED']:.0f}" if not pd.isna(p.get("MINUTES_PLAYED")) else "-"
        pts = _safe_int(p.get("PTS"))
        reb = _safe_int(p.get("REB"))
        ast = _safe_int(p.get("AST"))
        gs = p.get("GAME_SCORE")
        gs_str = f"{gs:.1f}" if not pd.isna(gs) else "-"
        gs_delta = p.get("GAME_SCORE_DELTA_L10")
        gs_delta_str = _fmt_delta(gs_delta)
        gs_delta_cls = _delta_cls(gs_delta)
        grade = p.get("PERFORMANCE_GRADE", "C")

        gs_color = "neutral"
        if not pd.isna(gs):
            if gs >= 15:
                gs_color = "positive"
            elif gs < 5:
                gs_color = "negative"

        html += (
            f'<div class="grade-player-row">'
            f'<span class="grade-player-name">{name}</span>'
            f'<span class="grade-player-stat dimmed">{mins}</span>'
            f'<span class="grade-player-stat">{pts}</span>'
            f'<span class="grade-player-stat">{reb}</span>'
            f'<span class="grade-player-stat">{ast}</span>'
            f'<span class="grade-player-gs {gs_color}">{gs_str}</span>'
            f'<span class="grade-player-delta {gs_delta_cls}">{gs_delta_str}</span>'
            f'<span class="grade-player-grade">{_render_grade_badge(grade, "small")}</span>'
            f'</div>'
        )

    return html


if not player_grades.empty:
    st.markdown(
        '<div class="section-header">PLAYER GRADES</div>',
        unsafe_allow_html=True,
    )

    left_col, right_col = st.columns(2)
    with left_col:
        st.markdown(
            _render_player_table(selected_game_id, is_home=False),
            unsafe_allow_html=True,
        )
    with right_col:
        st.markdown(
            _render_player_table(selected_game_id, is_home=True),
            unsafe_allow_html=True,
        )
