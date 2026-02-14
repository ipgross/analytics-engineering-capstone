"""Dialog content for the expanded game detail view."""

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st
import pandas as pd

from data.teams import get_logo_url, get_team_abbrev
from queries.games import (
    get_plays_for_game,
    get_predictions_for_game,
    get_ats_records,
    get_matchup_stats,
    get_recent_results,
    get_h2h_series,
    get_rest_days,
    get_box_score_for_game,
    get_live_odds_for_game,
    get_team_box_score_for_game,
)


# ── Game header (top of dialog) ────────────────────────────────────────────


def render_game_header(game: dict):
    """Render scoreboard header: logos, team names, scores, status."""
    away = game["VISITOR_TEAM_NAME"]
    home = game["HOME_TEAM_NAME"]
    away_score = int(game.get("VISITOR_TEAM_SCORE") or 0)
    home_score = int(game.get("HOME_TEAM_SCORE") or 0)
    status = game.get("STATUS") or ""

    away_logo = get_logo_url(away, 500)
    home_logo = get_logo_url(home, 500)

    is_final = status == "Final"
    period = int(game.get("PERIOD") or 0)
    show_scores = is_final or period > 0

    if is_final:
        away_cls = "winner" if away_score > home_score else "loser"
        home_cls = "winner" if home_score > away_score else "loser"
    else:
        away_cls = ""
        home_cls = ""

    # Status line — use descriptive labels like the game cards
    ordinals = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
    if is_final:
        status_html = '<div class="dialog-status">FINAL</div>'
    elif period > 0:
        clock = game.get("CLOCK") or ""
        if clock and ":" in clock:
            parts = clock.split()
            clock = parts[-1] if len(parts) > 1 else clock

        if "half" in status.lower():
            label = "Halftime"
            clock = ""
        elif period <= 4:
            label = f"{ordinals[period]} Qtr"
        else:
            label = f"OT{period - 4}"

        clock_display = f" {clock}" if clock else ""
        status_html = f'<div class="dialog-status live"><span class="live-dot"></span>{label}{clock_display}</div>'
    else:
        # Parse UTC timestamp to ET start time (e.g. "9:00 PM ET")
        et_label = status
        try:
            utc_dt = datetime.fromisoformat(status.replace("Z", "+00:00"))
            et_dt = utc_dt.astimezone(ZoneInfo("America/New_York"))
            et_label = et_dt.strftime("%I:%M %p ET").lstrip("0")
        except (ValueError, TypeError):
            pass
        status_html = f'<div class="dialog-status">{et_label}</div>'

    away_score_display = str(away_score) if show_scores else ""
    home_score_display = str(home_score) if show_scores else ""

    # Quarter columns — base Q1-Q4, plus OT column if overtime
    qtrs = ["1", "2", "3", "4"]
    qtr_heads = "".join(f'<span class="gd-q">{q}</span>' for q in qtrs)
    away_qtrs = "".join(
        f'<span class="gd-q">{_q(game, f"VISITOR_Q{q}", period)}</span>' for q in qtrs
    )
    home_qtrs = "".join(
        f'<span class="gd-q">{_q(game, f"HOME_Q{q}", period)}</span>' for q in qtrs
    )

    # Add OT column when game is in overtime or finished in OT
    if period > 4 or (is_final and _has_ot(game)):
        qtr_heads += '<span class="gd-q">OT</span>'
        away_ot = _ot_score(game, "VISITOR", away_score)
        home_ot = _ot_score(game, "HOME", home_score)
        away_qtrs += f'<span class="gd-q">{away_ot}</span>'
        home_qtrs += f'<span class="gd-q">{home_ot}</span>'

    header_html = f"""<div class="gd-header">
  {status_html}
  <div class="gd-row gd-row-head">
    <span class="gd-team-cell"></span>
    {qtr_heads}
    <span class="gd-total">T</span>
  </div>
  <div class="gd-row {away_cls}">
    <span class="gd-team-cell">
      <img src="{away_logo}" class="gd-logo">
      <span class="gd-name">{away}</span>
    </span>
    {away_qtrs}
    <span class="gd-total">{away_score_display}</span>
  </div>
  <div class="gd-row {home_cls}">
    <span class="gd-team-cell">
      <img src="{home_logo}" class="gd-logo">
      <span class="gd-name">{home}</span>
    </span>
    {home_qtrs}
    <span class="gd-total">{home_score_display}</span>
  </div>
</div>"""
    st.markdown(header_html, unsafe_allow_html=True)


# ── Play-by-Play tab ──────────────────────────────────────────────────────


def render_play_by_play_tab(game: dict):
    """Render play-by-play feed, most recent first, grouped by period.

    All plays are batched into a single HTML block so the scoring-play
    background spans the full row width without Streamlit container clipping.
    """
    game_id = int(game["GAME_ID"])
    plays_df = get_plays_for_game(game_id)

    if plays_df.empty:
        st.info("No play-by-play data available for this game.")
        return

    home_team = game["HOME_TEAM_NAME"]
    away_team = game["VISITOR_TEAM_NAME"]
    home_abbr = get_team_abbrev(home_team)
    away_abbr = get_team_abbrev(away_team)

    periods = sorted(plays_df["PERIOD"].unique(), reverse=True)

    # Build entire feed as one HTML string
    parts: list[str] = []
    for period in periods:
        period_plays = plays_df[plays_df["PERIOD"] == period]
        label = _get_period_label(period, period_plays)
        parts.append(f'<div class="pbp-period-header">{label}</div>')

        for _, play in period_plays.iterrows():
            parts.append(
                _build_play_html(play, home_team, away_team, home_abbr, away_abbr)
            )

    st.markdown("\n".join(parts), unsafe_allow_html=True)


def _build_play_html(
    play: pd.Series,
    home_team: str,
    away_team: str,
    home_abbr: str,
    away_abbr: str,
) -> str:
    """Return HTML for a single play-by-play row."""
    clock = play.get("CLOCK") or ""
    desc = play.get("DESCRIPTION") or play.get("ACTION_TYPE") or ""
    action_type = play.get("ACTION_TYPE") or ""
    team_name = play.get("TEAM_NAME")
    is_scoring = bool(play.get("SCORING_PLAY"))
    home_score = int(play.get("HOME_SCORE") or 0)
    away_score = int(play.get("AWAY_SCORE") or 0)

    if team_name and team_name == home_team:
        indicator_color = "#1d428a"
    elif team_name and team_name == away_team:
        indicator_color = "#C8102E"
    else:
        indicator_color = "#6B7280"

    scoring_cls = " pbp-scoring" if is_scoring else ""
    score_weight = "700" if is_scoring else "400"
    team_abbr = get_team_abbrev(team_name) if team_name else ""

    emoji = _play_emoji(desc, action_type, is_scoring)
    emoji_html = f'<span class="pbp-emoji">{emoji}</span>'

    score_display = f"{away_abbr} {away_score} - {home_score} {home_abbr}"

    return f"""<div class="pbp-play{scoring_cls}">
  <span class="pbp-clock">{clock}</span>
  <span class="pbp-indicator" style="background:{indicator_color};"></span>
  <span class="pbp-team">{team_abbr}</span>
  {emoji_html}
  <span class="pbp-desc">{desc}</span>
  <span class="pbp-score" style="font-weight:{score_weight};">{score_display}</span>
</div>"""


def _get_period_label(period: int, period_plays: pd.DataFrame) -> str:
    """Get human-readable period label."""
    display_vals = period_plays["PERIOD_DISPLAY"].dropna().unique()
    if len(display_vals) > 0:
        return str(display_vals[0])
    if period <= 4:
        ordinals = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
        return f"{ordinals.get(period, str(period))} Quarter"
    return f"Overtime {period - 4}"


# ── Summary tab ───────────────────────────────────────────────────────────


def _season_range(season_val) -> str:
    """Convert BallDontLie integer season to range format ('2025-26').

    BDL uses the starting year: season=2025 means the 2025-26 NBA season.
    The dbt mart tables use the '2025-26' range format from config.py.
    """
    try:
        year = int(season_val)
    except (TypeError, ValueError):
        return str(season_val or "")
    return f"{year}-{str(year + 1)[2:]}"


def render_matchup_tab(game: dict):
    """Render matchup tab: ATS records, team stats, H2H, recent results."""
    home = game["HOME_TEAM_NAME"]
    away = game["VISITOR_TEAM_NAME"]
    season = _season_range(game.get("SEASON"))
    game_date = game.get("GAME_DATE")

    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)

    parts: list[str] = []

    # Section 0: Rest days banner
    rest = get_rest_days(game_date, home, away)
    if rest:
        parts.append(
            _build_rest_days_banner(
                home, away, home_abbr, away_abbr, home_logo, away_logo, rest,
            )
        )

    # Section 1: ATS Records
    ats_df = get_ats_records(season, home, away)
    parts.append(
        _build_ats_section(
            ats_df, home, away, home_abbr, away_abbr, home_logo, away_logo,
        )
    )

    # Section 2: Team Matchup Stats
    stats_df = get_matchup_stats(season, home, away)
    parts.append(
        _build_matchup_stats_section(
            stats_df, home, away, home_abbr, away_abbr, home_logo, away_logo,
        )
    )

    # Section 3: Head-to-Head Season Series
    h2h_df = get_h2h_series(season, home, away)
    if not h2h_df.empty:
        parts.append(
            _build_h2h_section(
                h2h_df, home, away, home_abbr, away_abbr, home_logo, away_logo,
            )
        )

    st.markdown("\n".join(parts), unsafe_allow_html=True)

    # Section 4: Recent Results (uses st.columns for side-by-side)
    _render_recent_results(
        season, game_date, home, away, home_abbr, away_abbr, home_logo, away_logo,
    )


# ── Matchup tab builders ─────────────────────────────────────────────────


def _build_matchup_header(
    title: str,
    away_abbr: str, home_abbr: str,
    away_logo: str, home_logo: str,
) -> str:
    """Build section header with team logos on each side."""
    return (
        f'<div class="mu-header">'
        f'<div class="mu-team-badge">'
        f'<img src="{away_logo}" class="mu-team-logo">'
        f'<span class="mu-team-name">{away_abbr}</span>'
        f'</div>'
        f'<span class="mu-section-title">{title}</span>'
        f'<div class="mu-team-badge">'
        f'<span class="mu-team-name">{home_abbr}</span>'
        f'<img src="{home_logo}" class="mu-team-logo">'
        f'</div>'
        f'</div>'
    )


def _build_matchup_row(
    label: str,
    away_val: str, home_val: str,
    away_better: bool = False, home_better: bool = False,
    away_rank: str = "", home_rank: str = "",
    away_num: float | None = None, home_num: float | None = None,
    lower_is_better: bool = False,
) -> str:
    """Build a comparison row: away value | label | home value.

    When away_num/home_num are provided, renders a proportional bar below the label.
    """
    away_cls = " mu-advantage" if away_better else ""
    home_cls = " mu-advantage" if home_better else ""
    away_rank_html = f'<span class="mu-rank">({away_rank})</span>' if away_rank else ""
    home_rank_html = f'<span class="mu-rank">({home_rank})</span>' if home_rank else ""

    # Build center content: label + optional bar
    if away_num is not None and home_num is not None:
        total = abs(away_num) + abs(home_num)
        if total > 0:
            a_pct = (abs(away_num) / total) * 100
        else:
            a_pct = 50.0
        h_pct = 100 - a_pct
        if lower_is_better:
            a_bar_cls = " mu-advantage" if away_num < home_num else ""
            h_bar_cls = " mu-advantage" if home_num < away_num else ""
        else:
            a_bar_cls = " mu-advantage" if away_num > home_num else ""
            h_bar_cls = " mu-advantage" if home_num > away_num else ""
        center_html = (
            f'<div class="mu-row-center">'
            f'<div class="mu-label">{label}</div>'
            f'<div class="mu-bar">'
            f'<div class="mu-bar-left{a_bar_cls}" style="width:{a_pct:.1f}%"></div>'
            f'<div class="mu-bar-right{h_bar_cls}" style="width:{h_pct:.1f}%"></div>'
            f'</div></div>'
        )
    else:
        center_html = f'<div class="mu-label">{label}</div>'

    return (
        f'<div class="mu-row">'
        f'<div class="mu-val mu-left{away_cls}">{away_val} {away_rank_html}</div>'
        f'{center_html}'
        f'<div class="mu-val mu-right{home_cls}">{home_rank_html} {home_val}</div>'
        f'</div>'
    )


def _build_matchup_sub_row(label: str, away_val: str, home_val: str) -> str:
    """Build an indented sub-row for home/away splits."""
    return (
        f'<div class="mu-sub-row">'
        f'<div class="mu-sub-val mu-left">{away_val}</div>'
        f'<div class="mu-sub-label">{label}</div>'
        f'<div class="mu-sub-val mu-right">{home_val}</div>'
        f'</div>'
    )


def _ordinal(n: int) -> str:
    """Convert integer to ordinal string (1st, 2nd, 3rd, etc.)."""
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd'][min(n % 10, 4)] if n % 10 < 4 else 'th'}"


def _build_rest_days_banner(
    home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
    rest: dict,
) -> str:
    """Build rest days comparison banner."""
    away_rest = rest.get(away)
    home_rest = rest.get(home)
    if away_rest is None and home_rest is None:
        return ""

    def _rest_display(days):
        if days is None:
            return "N/A", ""
        if days == 0:
            return "B2B", " b2b"
        if days == 1:
            return "1 day", ""
        return f"{days} days", " advantage" if days >= 3 else ""

    away_disp, away_cls = _rest_display(away_rest)
    home_disp, home_cls = _rest_display(home_rest)

    # Mark advantage on the team with more rest
    if away_rest is not None and home_rest is not None:
        if away_rest > home_rest and away_rest >= 2:
            away_cls = " advantage"
            home_cls = ""
        elif home_rest > away_rest and home_rest >= 2:
            home_cls = " advantage"
            away_cls = ""

    return (
        f'<div class="mu-banner">'
        f'<div class="mu-banner-item">'
        f'<img src="{away_logo}">'
        f'<span>{away_abbr}</span>'
        f'<span class="mu-banner-value{away_cls}">{away_disp}</span>'
        f'</div>'
        f'<span class="mu-banner-label">Rest</span>'
        f'<div class="mu-banner-item">'
        f'<span class="mu-banner-value{home_cls}">{home_disp}</span>'
        f'<span>{home_abbr}</span>'
        f'<img src="{home_logo}">'
        f'</div>'
        f'</div>'
    )


def _build_ats_section(
    ats_df: pd.DataFrame,
    home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
) -> str:
    """Build the ATS Records section."""
    parts = ['<div class="mu-section">']
    parts.append(_build_matchup_header("ATS Records", away_abbr, home_abbr, away_logo, home_logo))

    if ats_df.empty:
        parts.append('<div class="mu-label" style="padding:16px 0;">No records available</div>')
        parts.append("</div>")
        return "\n".join(parts)

    away_row = ats_df[ats_df["TEAM_NAME"] == away]
    home_row = ats_df[ats_df["TEAM_NAME"] == home]
    if away_row.empty or home_row.empty:
        parts.append('<div class="mu-label" style="padding:16px 0;">No records available</div>')
        parts.append("</div>")
        return "\n".join(parts)

    a = away_row.iloc[0].to_dict()
    h = home_row.iloc[0].to_dict()

    # ATS record
    a_ats = f"{int(a['ATS_WINS'])}-{int(a['ATS_LOSSES'])}"
    h_ats = f"{int(h['ATS_WINS'])}-{int(h['ATS_LOSSES'])}"
    a_ats_pct = _safe_float(a.get("ATS_PCT"), 0)
    h_ats_pct = _safe_float(h.get("ATS_PCT"), 0)
    a_ats_rank = _ordinal(int(a["ATS_RANK"])) if not _is_missing(a.get("ATS_RANK")) else ""
    h_ats_rank = _ordinal(int(h["ATS_RANK"])) if not _is_missing(h.get("ATS_RANK")) else ""
    parts.append(_build_matchup_row(
        "Against the Spread", a_ats, h_ats,
        away_better=a_ats_pct > h_ats_pct, home_better=h_ats_pct > a_ats_pct,
        away_rank=a_ats_rank, home_rank=h_ats_rank,
    ))

    # ATS home/away splits
    a_home_ats = f"{int(a.get('HOME_ATS_WINS') or 0)}-{int(a.get('HOME_ATS_LOSSES') or 0)}"
    a_away_ats = f"{int(a.get('AWAY_ATS_WINS') or 0)}-{int(a.get('AWAY_ATS_LOSSES') or 0)}"
    h_home_ats = f"{int(h.get('HOME_ATS_WINS') or 0)}-{int(h.get('HOME_ATS_LOSSES') or 0)}"
    h_away_ats = f"{int(h.get('AWAY_ATS_WINS') or 0)}-{int(h.get('AWAY_ATS_LOSSES') or 0)}"
    # Away team shows their away record, home team shows their home record
    parts.append(_build_matchup_sub_row("Home / Away", f"{a_home_ats} / {a_away_ats}", f"{h_home_ats} / {h_away_ats}"))

    # SU record
    a_su = f"{int(a['SU_WINS'])}-{int(a['SU_LOSSES'])}"
    h_su = f"{int(h['SU_WINS'])}-{int(h['SU_LOSSES'])}"
    a_su_pct = _safe_float(a.get("SU_PCT"), 0)
    h_su_pct = _safe_float(h.get("SU_PCT"), 0)
    a_su_rank = _ordinal(int(a["SU_RANK"])) if not _is_missing(a.get("SU_RANK")) else ""
    h_su_rank = _ordinal(int(h["SU_RANK"])) if not _is_missing(h.get("SU_RANK")) else ""
    parts.append(_build_matchup_row(
        "Straight Up", a_su, h_su,
        away_better=a_su_pct > h_su_pct, home_better=h_su_pct > a_su_pct,
        away_rank=a_su_rank, home_rank=h_su_rank,
    ))

    # SU home/away splits
    a_home_su = f"{int(a.get('HOME_SU_WINS') or 0)}-{int(a.get('HOME_SU_LOSSES') or 0)}"
    a_away_su = f"{int(a.get('AWAY_SU_WINS') or 0)}-{int(a.get('AWAY_SU_LOSSES') or 0)}"
    h_home_su = f"{int(h.get('HOME_SU_WINS') or 0)}-{int(h.get('HOME_SU_LOSSES') or 0)}"
    h_away_su = f"{int(h.get('AWAY_SU_WINS') or 0)}-{int(h.get('AWAY_SU_LOSSES') or 0)}"
    parts.append(_build_matchup_sub_row("Home / Away", f"{a_home_su} / {a_away_su}", f"{h_home_su} / {h_away_su}"))

    # O/U record
    a_over = int(a.get("OVER_WINS") or 0)
    a_under = int(a.get("UNDER_WINS") or 0)
    h_over = int(h.get("OVER_WINS") or 0)
    h_under = int(h.get("UNDER_WINS") or 0)
    a_ou = f"{a_over}-{a_under}"
    h_ou = f"{h_over}-{h_under}"
    parts.append(_build_matchup_row(
        "Over / Under", a_ou, h_ou,
        away_better=a_over > a_under, home_better=h_over > h_under,
    ))

    parts.append("</div>")
    return "\n".join(parts)


def _build_matchup_stats_section(
    stats_df: pd.DataFrame,
    home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
) -> str:
    """Build the Team Matchup stats comparison section."""
    parts = ['<div class="mu-section">']
    parts.append(_build_matchup_header("Team Matchup", away_abbr, home_abbr, away_logo, home_logo))

    if stats_df.empty:
        parts.append('<div class="mu-label" style="padding:16px 0;">No stats available</div>')
        parts.append("</div>")
        return "\n".join(parts)

    away_row = stats_df[stats_df["TEAM_NAME"] == away]
    home_row = stats_df[stats_df["TEAM_NAME"] == home]
    if away_row.empty or home_row.empty:
        parts.append('<div class="mu-label" style="padding:16px 0;">No stats available</div>')
        parts.append("</div>")
        return "\n".join(parts)

    a = away_row.iloc[0].to_dict()
    h = home_row.iloc[0].to_dict()

    def _stat_row(label: str, col: str, fmt: str = ".1f", lower_is_better: bool = False):
        av = _safe_float(a.get(col))
        hv = _safe_float(h.get(col))
        if av is None or hv is None:
            return ""
        a_disp = f"{av:{fmt}}"
        h_disp = f"{hv:{fmt}}"
        if fmt.endswith("%"):
            a_disp = f"{av * 100:.0f}%"
            h_disp = f"{hv * 100:.0f}%"
        if lower_is_better:
            ab, hb = av < hv, hv < av
        else:
            ab, hb = av > hv, hv > av
        return _build_matchup_row(
            label, a_disp, h_disp, away_better=ab, home_better=hb,
            away_num=av, home_num=hv, lower_is_better=lower_is_better,
        )

    def _pct_row(label: str, col: str, lower_is_better: bool = False):
        av = _safe_float(a.get(col))
        hv = _safe_float(h.get(col))
        if av is None or hv is None:
            return ""
        a_disp = f"{av * 100:.0f}%" if av < 1 else f"{av:.0f}%"
        h_disp = f"{hv * 100:.0f}%" if hv < 1 else f"{hv:.0f}%"
        if lower_is_better:
            ab, hb = av < hv, hv < av
        else:
            ab, hb = av > hv, hv > av
        return _build_matchup_row(
            label, a_disp, h_disp, away_better=ab, home_better=hb,
            away_num=av, home_num=hv, lower_is_better=lower_is_better,
        )

    # Scoring
    parts.append(_stat_row("Points", "AVG_PTS"))
    parts.append(_stat_row("Field Goals Made", "AVG_FGM"))
    parts.append(_stat_row("Field Goals Attempted", "AVG_FGA"))
    parts.append(_pct_row("Field Goal Percentage", "AVG_FG_PCT"))

    # Three-Point
    parts.append(_stat_row("3 Point Field Goals Made", "AVG_FG3M"))
    parts.append(_stat_row("3 Point Field Goals Attempted", "AVG_FG3A"))
    parts.append(_pct_row("3 Point Field Goal Percentage", "AVG_FG3_PCT"))

    # Free Throw
    parts.append(_stat_row("Free Throws Made", "AVG_FTM"))
    parts.append(_stat_row("Free Throws Attempted", "AVG_FTA"))
    parts.append(_pct_row("Free Throw Percentage", "AVG_FT_PCT"))

    # Advanced / Pace
    parts.append(_stat_row("Possessions", "AVG_POSSESSIONS"))

    # Rebounding
    parts.append(_stat_row("Rebounds", "AVG_REB"))
    parts.append(_stat_row("Offensive Rebounds", "AVG_OREB"))
    parts.append(_stat_row("Defensive Rebounds", "AVG_DREB"))

    # Playmaking
    parts.append(_stat_row("Assists", "AVG_AST"))
    parts.append(_stat_row("Turnovers", "AVG_TURNOVERS", lower_is_better=True))

    # Defense
    parts.append(_stat_row("Steals", "AVG_STL"))
    parts.append(_stat_row("Blocks", "AVG_BLK"))
    parts.append(_stat_row("Personal Fouls", "AVG_PF", lower_is_better=True))

    # Ratings
    parts.append(_stat_row("Defensive Rating", "AVG_DEF_RATING", lower_is_better=True))
    parts.append(_stat_row("Offensive Rating", "AVG_OFF_RATING"))

    parts.append("</div>")
    return "\n".join(parts)


def _build_h2h_section(
    h2h_df: pd.DataFrame,
    home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
) -> str:
    """Build the Head-to-Head season series section as a table."""
    parts = ['<div class="mu-section">']
    parts.append(_build_matchup_header("Season Series", away_abbr, home_abbr, away_logo, home_logo))

    # Column headers
    parts.append(
        '<div class="mu-h2h-row mu-h2h-col-hdr">'
        '<span class="mu-h2h-matchup">Matchup</span>'
        '<span class="mu-h2h-col su">SU</span>'
        '<span class="mu-h2h-col ats">ATS</span>'
        '<span class="mu-h2h-col ou">O/U</span>'
        '</div>'
    )

    for _, row in h2h_df.iterrows():
        gd = row["GAME_DATE"]
        if hasattr(gd, "strftime"):
            try:
                date_str = gd.strftime("%b %-d, %Y")
            except ValueError:
                date_str = gd.strftime("%b %d, %Y").replace(" 0", " ")
        else:
            date_str = str(gd)

        h_name = row["HOME_TEAM_NAME"]
        v_name = row["VISITOR_TEAM_NAME"]
        h_score = int(row["HOME_TEAM_SCORE"])
        v_score = int(row["VISITOR_TEAM_SCORE"])
        h_abbr_local = get_team_abbrev(h_name)
        v_abbr_local = get_team_abbrev(v_name)
        matchup_str = f"{v_name} @ {h_name}"
        score_str = f"{v_score}-{h_score}"

        # SU winner badge
        winner = row.get("WINNER") or ""
        winner_abbr = get_team_abbrev(winner) if winner and winner != "TIE" else ""
        su_badge = f'<span class="mu-h2h-badge win">{winner_abbr}</span>' if winner_abbr else ""

        # ATS: who covered + spread line
        home_res = row.get("HOME_SPREAD_RESULT") or ""
        away_res = row.get("AWAY_SPREAD_RESULT") or ""
        home_spread = _safe_float(row.get("HOME_SPREAD"))
        away_spread = _safe_float(row.get("AWAY_SPREAD"))

        ats_val = ""
        ats_badge = ""
        if home_res == "COVERED":
            ats_badge = f'<span class="mu-h2h-badge win">{h_abbr_local}</span>'
            if home_spread is not None:
                sign = "+" if home_spread > 0 else ""
                ats_val = f"{sign}{home_spread:g}"
        elif away_res == "COVERED":
            ats_badge = f'<span class="mu-h2h-badge win">{v_abbr_local}</span>'
            if away_spread is not None:
                sign = "+" if away_spread > 0 else ""
                ats_val = f"{sign}{away_spread:g}"
        elif home_res == "PUSH":
            ats_badge = '<span class="mu-h2h-badge push">PUSH</span>'
            if home_spread is not None:
                sign = "+" if home_spread > 0 else ""
                ats_val = f"{sign}{home_spread:g}"

        # O/U: total as % of line
        ou_res = row.get("OVER_RESULT") or ""
        total = _safe_float(row.get("TOTAL_POINTS"))
        total_line = _safe_float(row.get("TOTAL_LINE"))
        ou_val = ""
        ou_badge = ""
        if ou_res and total is not None and total_line is not None and total_line > 0:
            pct = total / total_line * 100
            ou_val = f"{pct:.0f}%"
            if ou_res == "COVERED":
                ou_badge = '<span class="mu-h2h-badge over">O</span>'
            elif ou_res == "MISSED":
                ou_badge = '<span class="mu-h2h-badge under">U</span>'
            else:
                ou_badge = '<span class="mu-h2h-badge push">P</span>'

        parts.append(
            f'<div class="mu-h2h-row">'
            f'<span class="mu-h2h-matchup">'
            f'<span class="mu-h2h-teams">{matchup_str}</span>'
            f'<span class="mu-h2h-date">{date_str}</span>'
            f'</span>'
            f'<span class="mu-h2h-col su">'
            f'<span class="mu-h2h-val">{score_str}</span>{su_badge}'
            f'</span>'
            f'<span class="mu-h2h-col ats">'
            f'<span class="mu-h2h-val">{ats_val}</span>{ats_badge}'
            f'</span>'
            f'<span class="mu-h2h-col ou">'
            f'<span class="mu-h2h-val">{ou_val}</span>{ou_badge}'
            f'</span>'
            f'</div>'
        )

    parts.append("</div>")
    return "\n".join(parts)


def _render_recent_results(
    season: str,
    game_date,
    home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
):
    """Render Recent Results section using st.columns for side-by-side layout."""
    st.markdown(
        '<div class="mu-section">'
        '<div class="mu-header">'
        f'<div class="mu-team-badge">'
        f'<img src="{away_logo}" class="mu-team-logo">'
        f'<span class="mu-team-name">{away_abbr}</span></div>'
        f'<span class="mu-section-title">Recent Results</span>'
        f'<div class="mu-team-badge">'
        f'<span class="mu-team-name">{home_abbr}</span>'
        f'<img src="{home_logo}" class="mu-team-logo"></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )

    away_df = get_recent_results(season, away, game_date)
    home_df = get_recent_results(season, home, game_date)

    col_away, col_home = st.columns(2)

    with col_away:
        _render_team_recent(away_df, away, away_abbr)

    with col_home:
        _render_team_recent(home_df, home, home_abbr)


def _render_team_recent(
    df: pd.DataFrame, team: str, abbr: str,
):
    """Render one team's recent results column as a table."""
    if df.empty:
        st.caption("No recent results")
        return

    wins = len(df[df["RESULT"] == "W"])
    losses = len(df) - wins

    parts = [
        f'<div class="mu-recent-header">'
        f'<span class="mu-recent-header-name">{team}</span>'
        f'<span class="mu-recent-header-record">L{len(df)}: {wins}-{losses}</span>'
        f'</div>',
        # Column headers
        '<div class="mu-recent-row mu-recent-col-hdr">'
        '<span class="mu-recent-game">GAME</span>'
        '<span class="mu-recent-score-col">SCORE</span>'
        '<span class="mu-recent-ats-col">ATS</span>'
        '<span class="mu-recent-ou-col">O/U</span>'
        '</div>',
    ]

    for _, row in df.iterrows():
        gd = row["GAME_DATE"]
        if hasattr(gd, "strftime"):
            try:
                date_str = gd.strftime("%b %-d, %Y")
            except ValueError:
                date_str = gd.strftime("%b %d, %Y").replace(" 0", " ")
        else:
            date_str = str(gd)

        opp = row["OPPONENT"]
        venue = row["VENUE"]
        prefix = "at " if venue == "away" else "vs "

        result = row["RESULT"]
        wl_cls = "win" if result == "W" else "loss"

        team_score = int(row["TEAM_SCORE"])
        opp_score = int(row["OPP_SCORE"])
        score_str = f"{team_score}-{opp_score}"

        # ATS badge
        ats = row.get("ATS_RESULT") or ""
        spread = _safe_float(row.get("SPREAD"))
        if ats in ("COVERED", "MISSED", "PUSH"):
            ats_cls = ats.lower()
            if spread is not None:
                sign = "+" if spread > 0 else ""
                ats_disp = f"{sign}{spread:g}"
            else:
                ats_disp = ats[:3]
        else:
            ats_cls = ""
            ats_disp = ""
        ats_badge = f'<span class="mu-recent-badge {ats_cls}">{ats_disp}</span>' if ats_disp else ""

        # O/U badge
        ou = row.get("OVER_RESULT") or ""
        total = _safe_float(row.get("TOTAL_POINTS"))
        total_line = _safe_float(row.get("TOTAL_LINE"))
        if ou in ("COVERED", "MISSED", "PUSH") and total_line is not None and total is not None:
            pct = (total / total_line * 100) if total_line > 0 else 0
            ou_cls = "over" if ou == "COVERED" else "under" if ou == "MISSED" else "push"
            ou_disp = f"{pct:.0f}%"
        else:
            ou_cls = ""
            ou_disp = ""
        ou_badge = f'<span class="mu-recent-badge {ou_cls}">{ou_disp}</span>' if ou_disp else ""

        parts.append(
            f'<div class="mu-recent-row">'
            f'<span class="mu-recent-game">'
            f'<span class="mu-recent-opp-name">{prefix}{opp}</span>'
            f'<span class="mu-recent-date">{date_str}</span>'
            f'</span>'
            f'<span class="mu-recent-score-col">'
            f'<span class="mu-recent-wl {wl_cls}">{result}</span>'
            f'<span class="mu-recent-score">{score_str}</span>'
            f'</span>'
            f'<span class="mu-recent-ats-col">{ats_badge}</span>'
            f'<span class="mu-recent-ou-col">{ou_badge}</span>'
            f'</div>'
        )

    st.markdown("\n".join(parts), unsafe_allow_html=True)


def _q(game: dict, key: str, current_period: int = 0) -> str:
    """Format a quarter score, returning blank for unplayed quarters."""
    qtr_num = int(key[-1])
    if current_period > 0 and qtr_num > current_period:
        return ""
    val = game.get(key)
    if val is None:
        return "-"
    try:
        return str(int(val))
    except (ValueError, TypeError):
        return "-"


def _has_ot(game: dict) -> bool:
    """Check if a game went to overtime using explicit OT columns.

    Falls back to comparing total vs Q1-Q4 sum when OT columns are NULL.
    """
    # Prefer explicit OT columns
    for side in ("HOME", "VISITOR"):
        ot1 = game.get(f"{side}_OT1")
        if ot1 is not None and not _is_missing(ot1) and int(ot1) > 0:
            return True
    # Fallback: total > sum of Q1-Q4
    try:
        for side in ("HOME", "VISITOR"):
            total = int(game.get(f"{side}_TEAM_SCORE") or 0)
            q_sum = sum(int(game.get(f"{side}_Q{q}") or 0) for q in range(1, 5))
            if total > q_sum:
                return True
    except (ValueError, TypeError):
        pass
    return False


def _ot_score(game: dict, side_prefix: str, total_score: int) -> str:
    """Get OT points using explicit OT columns.

    Falls back to computing from total minus Q1-Q4 sum when OT columns are NULL.
    """
    # Prefer explicit OT columns: sum OT1 + OT2 + OT3
    ot_total = 0
    has_ot_cols = False
    for ot_num in (1, 2, 3):
        val = game.get(f"{side_prefix}_OT{ot_num}")
        if val is not None and not _is_missing(val):
            has_ot_cols = True
            ot_total += int(val)
    if has_ot_cols:
        return str(ot_total)
    # Fallback: total - Q1-Q4 sum
    try:
        q_sum = sum(int(game.get(f"{side_prefix}_Q{q}") or 0) for q in range(1, 5))
        ot = total_score - q_sum
        return str(ot) if ot >= 0 else "-"
    except (ValueError, TypeError):
        return "-"


def _play_emoji(desc: str, action_type: str, is_scoring: bool) -> str:
    """Return an emoji prefix for common play types."""
    d = desc.lower()
    a = (action_type or "").lower()

    if is_scoring:
        if "3pt" in a or "3-pointer" in d or "three point" in d or "3pt" in d:
            return "\U0001F3AF"  # 🎯 three-pointer
        if "free throw" in d or "freethrow" in a:
            return "\u2705"  # ✅ made free throw
        if "dunk" in d:
            return "\U0001F4A5"  # 💥 dunk
        return "\U0001F3C0"  # 🏀 generic made shot

    if "misses" in d or "missed" in d:
        if "free throw" in d:
            return "\u274C"  # ❌ missed FT
        return "\u274C"  # ❌ missed shot

    if "rebound" in d or "rebound" in a:
        return "\U0001F4AA"  # 💪 rebound

    if "block" in d or "block" in a:
        return "\U0001F6AB"  # 🚫 block

    if "steal" in d or "steal" in a:
        return "\U0001F4A8"  # 💨 steal

    if "turnover" in d or "turnover" in a:
        return "\U0001F4AB"  # 💫 turnover

    if "foul" in d or "foul" in a:
        return "\u26A0\uFE0F"  # ⚠️ foul

    if "timeout" in d or "timeout" in a:
        return "\u23F8\uFE0F"  # ⏸️ timeout

    if "enters the game" in d or "substitution" in a:
        return "\U0001F504"  # 🔄 substitution

    if "jump ball" in d or "jumpball" in a:
        return "\u2B06\uFE0F"  # ⬆️ jump ball

    if "end of" in d or "start of" in d or "period" in a:
        return "\U0001F514"  # 🔔 period marker

    if "violation" in d or "violation" in a:
        return "\U0001F6A9"  # 🚩 violation

    return ""


# ── Prediction tab ────────────────────────────────────────────────────────


def render_prediction_tab(game: dict):
    """Render full prediction analysis for all three betting markets."""
    game_date = game["GAME_DATE"]
    home_team = game["HOME_TEAM_NAME"]

    preds_df = get_predictions_for_game(game_date, home_team)

    if preds_df.empty:
        st.info("No prediction data available for this game.")
        return

    is_final = game.get("STATUS") == "Final"
    period = int(game.get("PERIOD") or 0)
    is_live = period > 0 and not is_final

    MARKET_OPTIONS = ["Spread", "H2H", "Totals"]
    MARKET_MAP = {"Spread": "spreads", "H2H": "h2h", "Totals": "totals"}

    market = st.segmented_control(
        "Market",
        options=MARKET_OPTIONS,
        default="Spread",
        label_visibility="collapsed",
        key="pred_market",
    )

    mk = MARKET_MAP.get(market, "spreads")
    market_df = preds_df[preds_df["MARKET_KEY"] == mk]
    if market_df.empty:
        st.caption("No data for this market.")
        return
    _render_market_prediction(game, market_df, mk, is_final, is_live)


def _render_market_prediction(
    game: dict,
    market_df: pd.DataFrame,
    market_key: str,
    is_final: bool,
    is_live: bool,
):
    """Render prediction analysis for a single market as one HTML block."""
    home = game["HOME_TEAM_NAME"]
    away = game["VISITOR_TEAM_NAME"]
    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)

    # ── Extract the two sides ──
    if market_key == "totals":
        row_a = market_df[market_df["SIDE"] == "Over"]
        row_b = market_df[market_df["SIDE"] == "Under"]
        label_a, label_b = "Over", "Under"
        logo_a, logo_b = "", ""
    else:
        row_a = market_df[market_df["SIDE"] == away]
        row_b = market_df[market_df["SIDE"] == home]
        label_a, label_b = away_abbr, home_abbr
        logo_a, logo_b = away_logo, home_logo

    if row_a.empty or row_b.empty:
        st.info("Incomplete prediction data.")
        return

    a = row_a.iloc[0].to_dict()  # away / Over
    b = row_b.iloc[0].to_dict()  # home / Under

    # Featured side = higher bet rating (the recommended bet)
    rat_a = _safe_float(a.get("BET_RATING"), 0)
    rat_b = _safe_float(b.get("BET_RATING"), 0)
    if rat_a >= rat_b:
        feat, feat_label, feat_logo = a, label_a, logo_a
    else:
        feat, feat_label, feat_logo = b, label_b, logo_b

    # ── Build HTML ──
    parts: list[str] = ['<div class="pred-grid">']

    # Card 1: Consensus Line (both sides)
    parts.append(_card_consensus_line(a, b, label_a, label_b, logo_a, logo_b, market_key))

    # Card 2: Score Projection
    parts.append(
        _card_projection(a, market_key, home_abbr, away_abbr, home_logo, away_logo)
    )

    # Card 3: Cover Probability
    parts.append(_card_cover_prob(feat, feat_label, feat_logo, market_key))

    # Card 4: Expected Value
    parts.append(_card_expected_value(feat, feat_label, feat_logo))

    # Card 5: Bet Rating
    parts.append(_card_bet_rating(feat, feat_label, feat_logo))

    # Card 6: Season Record (both teams)
    parts.append(
        _card_season_record(a, b, label_a, label_b, logo_a, logo_b, market_key)
    )

    parts.append("</div>")  # close pred-grid

    # ── Team Comparison Bars ──
    home_l10_pts = _safe_float(a.get("HOME_L10_PTS"))
    away_l10_pts = _safe_float(a.get("AWAY_L10_PTS"))
    home_l10_off = _safe_float(a.get("HOME_L10_OFF_RATING"))
    away_l10_off = _safe_float(a.get("AWAY_L10_OFF_RATING"))
    home_l10_def = _safe_float(a.get("HOME_L10_DEF_RATING"))
    away_l10_def = _safe_float(a.get("AWAY_L10_DEF_RATING"))

    if home_l10_pts is not None and away_l10_pts is not None:
        title = "Scoring Context (L10)" if market_key == "totals" else "L10 Team Comparison"
        parts.append(
            f'<div class="pred-compare">'
            f'<div class="pred-compare-header">'
            f'<span class="pred-compare-title">{title}</span>'
            f'<div class="pred-compare-legend">'
            f'<span><span class="pred-legend-dot" style="background:#1d428a;"></span>{home_abbr}</span>'
            f'<span><span class="pred-legend-dot" style="background:#C8102E;"></span>{away_abbr}</span>'
            f"</div></div>"
        )
        parts.append(_build_bar_row("PPG", home_l10_pts, away_l10_pts))
        if home_l10_off is not None and away_l10_off is not None:
            parts.append(_build_bar_row("Off Rtg", home_l10_off, away_l10_off))
        if home_l10_def is not None and away_l10_def is not None:
            parts.append(
                _build_bar_row("Def Rtg", home_l10_def, away_l10_def, lower_is_better=True)
            )
        parts.append("</div>")  # close pred-compare

    # ── Matchup Edge Callout ──
    parts.append(_build_edge_callout(feat, feat_label, market_key))

    # ── Final: Prediction vs Result ──
    if is_final:
        parts.append(_build_result_section(game, feat, feat_label, market_key))
    elif is_live:
        parts.append(
            '<div class="pred-live-note">Pre-game prediction \u2014 game is in progress</div>'
        )

    st.markdown("\n".join(parts), unsafe_allow_html=True)


# ── Prediction card builders ─────────────────────────────────────────────


def _card_consensus_line(
    a: dict, b: dict, label_a: str, label_b: str,
    logo_a: str, logo_b: str, market_key: str,
) -> str:
    """Build the Consensus Line card showing both sides."""
    logo_a_html = f'<img src="{logo_a}" class="pred-logo">' if logo_a else ""
    logo_b_html = f'<img src="{logo_b}" class="pred-logo">' if logo_b else ""

    if market_key == "h2h":
        disp_a = _fmt_price(a.get("CONSENSUS_PRICE"))
        disp_b = _fmt_price(b.get("CONSENSUS_PRICE"))
    else:
        line_a = _fmt_line(a.get("CONSENSUS_LINE"))
        line_b = _fmt_line(b.get("CONSENSUS_LINE"))
        disp_a = f"{line_a} ({_fmt_price(a.get('CONSENSUS_PRICE'))})"
        disp_b = f"{line_b} ({_fmt_price(b.get('CONSENSUS_PRICE'))})"

    books_a = _safe_float(a.get("NUM_BOOKMAKERS"))
    books_sub = ""
    if books_a is not None:
        books_sub = f'<div class="pred-projection-sub">{int(books_a)} bookmakers</div>'

    return (
        f'<div class="pred-card">'
        f'<div class="pred-card-label">Consensus Line</div>'
        f'<div class="pred-card-value">'
        f'<div class="pred-side">{logo_a_html}'
        f'<span class="pred-team">{label_a}</span>'
        f'<span class="pred-line">{disp_a}</span></div>'
        f'<div class="pred-side">{logo_b_html}'
        f'<span class="pred-team">{label_b}</span>'
        f'<span class="pred-line">{disp_b}</span></div>'
        f"{books_sub}"
        f"</div></div>"
    )


def _card_projection(
    row: dict, market_key: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
) -> str:
    """Build the Score Projection card with logos and winner highlight."""
    proj_home = _safe_float(row.get("PROJECTED_HOME_SCORE"))
    proj_away = _safe_float(row.get("PROJECTED_AWAY_SCORE"))
    proj_total = _safe_float(row.get("PROJECTED_TOTAL"))

    if market_key == "totals":
        if proj_total is not None:
            main = f'<div class="pred-projection">{proj_total:.1f}</div>'
            line_val = _safe_float(row.get("CONSENSUS_LINE"))
            if line_val is not None:
                diff = proj_total - line_val
                direction = "Over" if diff > 0 else "Under"
                sub = f"Line {line_val:.1f} &middot; Proj {direction} by {abs(diff):.1f}"
                main += f'<div class="pred-projection-sub">{sub}</div>'
        else:
            main = '<div class="pred-projection">N/A</div>'
    else:
        if proj_home is not None and proj_away is not None:
            margin = proj_home - proj_away
            home_win = " winner" if margin > 0 else ""
            away_win = " winner" if margin < 0 else ""

            main = (
                f'<div class="pred-proj-matchup">'
                f'<div class="pred-proj-side">'
                f'<img src="{away_logo}" class="pred-logo">'
                f'<span class="pred-proj-name">{away_abbr}</span>'
                f'<span class="pred-proj-score{away_win}">{proj_away:.0f}</span>'
                f'</div>'
                f'<span class="pred-proj-dash">&ndash;</span>'
                f'<div class="pred-proj-side">'
                f'<span class="pred-proj-score{home_win}">{proj_home:.0f}</span>'
                f'<span class="pred-proj-name">{home_abbr}</span>'
                f'<img src="{home_logo}" class="pred-logo">'
                f'</div></div>'
            )

            if abs(margin) < 0.5:
                main += '<div class="pred-proj-fav">Pick\'em</div>'
            else:
                fav_abbr = home_abbr if margin > 0 else away_abbr
                fav_logo_url = home_logo if margin > 0 else away_logo
                main += (
                    f'<div class="pred-proj-fav">'
                    f'<img src="{fav_logo_url}" class="pred-proj-fav-logo">'
                    f'{fav_abbr} favored by {abs(margin):.1f}'
                    f'</div>'
                )
        else:
            main = '<div class="pred-projection">N/A</div>'

    return (
        f'<div class="pred-card">'
        f'<div class="pred-card-label">Score Projection</div>'
        f'<div class="pred-card-value">{main}</div></div>'
    )


def _card_cover_prob(feat: dict, feat_label: str, feat_logo: str, market_key: str) -> str:
    """Build the Cover Probability card."""
    prob = _safe_float(feat.get("COVER_PROBABILITY"))
    if prob is not None:
        pct = f"{prob * 100:.1f}%"
        width = f"{prob * 100:.1f}%"
        bar_cls = "pred-pct-fill strong" if prob >= 0.55 else "pred-pct-fill"
    else:
        pct, width, bar_cls = "N/A", "0%", "pred-pct-fill"

    label_html = _feat_label_html(feat_label, feat_logo)
    return (
        f'<div class="pred-card">'
        f'<div class="pred-card-label">Cover Probability</div>'
        f'<div class="pred-card-value">'
        f'<span class="pred-pct-main">{pct}</span>'
        f'<div class="pred-pct-bar"><div class="{bar_cls}" style="width:{width}"></div></div>'
        f'{label_html}'
        f"</div></div>"
    )


def _card_expected_value(feat: dict, feat_label: str, feat_logo: str) -> str:
    """Build the Expected Value card."""
    ev = _safe_float(feat.get("EXPECTED_VALUE"))
    if ev is not None:
        ev_pct = ev * 100
        sign = "+" if ev_pct > 0 else ""
        ev_display = f"{sign}{ev_pct:.1f}%"
        ev_cls = "pred-ev positive" if ev >= 0 else "pred-ev negative"

        implied = _safe_float(feat.get("CONSENSUS_IMPLIED_PROB"))
        prob = _safe_float(feat.get("COVER_PROBABILITY"))
        if implied is not None and prob is not None:
            sub = f"Implied {implied * 100:.0f}% vs Model {prob * 100:.0f}%"
        else:
            sub = ""
    else:
        ev_display, ev_cls, sub = "N/A", "pred-ev", ""

    sub_html = f'<div class="pred-ev-sub">{sub}</div>' if sub else ""
    label_html = _feat_label_html(feat_label, feat_logo)
    return (
        f'<div class="pred-card">'
        f'<div class="pred-card-label">Expected Value</div>'
        f'<div class="pred-card-value">'
        f'<span class="{ev_cls}">{ev_display}</span>'
        f"{sub_html}"
        f'{label_html}'
        f"</div></div>"
    )


def _card_bet_rating(feat: dict, feat_label: str, feat_logo: str) -> str:
    """Build the Bet Rating card with 1-5 stars."""
    rating = _safe_float(feat.get("BET_RATING"))
    if rating is not None:
        stars_int = int(rating)
        filled = "\u2605" * stars_int
        empty = "\u2606" * (5 - stars_int)
        labels = {5: "Strong value", 4: "Good value", 3: "Slight edge",
                  2: "Marginal", 1: "No edge"}
        sub = labels.get(stars_int, "")
    else:
        filled, empty = "", "\u2606" * 5
        sub = ""

    label_html = _feat_label_html(feat_label, feat_logo)
    sub_html = f'<div class="pred-stars-sub">{sub}</div>' if sub else ""
    return (
        f'<div class="pred-card">'
        f'<div class="pred-card-label">Bet Rating</div>'
        f'<div class="pred-card-value">'
        f'<span class="pred-stars">{filled}{empty}</span>'
        f"{sub_html}"
        f'{label_html}'
        f"</div></div>"
    )


def _card_season_record(
    a: dict, b: dict, label_a: str, label_b: str,
    logo_a: str, logo_b: str, market_key: str,
) -> str:
    """Build the Season Record card showing both teams."""
    logo_a_html = f'<img src="{logo_a}" class="pred-logo">' if logo_a else ""
    logo_b_html = f'<img src="{logo_b}" class="pred-logo">' if logo_b else ""

    row_a = _fmt_season_row(a, label_a, logo_a_html)
    row_b = _fmt_season_row(b, label_b, logo_b_html)

    return (
        f'<div class="pred-card">'
        f'<div class="pred-card-label">Season Record</div>'
        f'<div class="pred-card-value">'
        f"{row_a}{row_b}"
        f"</div></div>"
    )


def _fmt_season_row(side: dict, label: str, logo_html: str) -> str:
    """Format one team's season record row."""
    wins = _safe_float(side.get("SEASON_MARKET_WINS"))
    total = _safe_float(side.get("SEASON_MARKET_TOTAL"))
    if wins is not None and total is not None and total > 0:
        w, t = int(wins), int(total)
        pct = w / t * 100
        val = (
            f'<span class="pred-record">{w}-{t - w}</span>'
            f'<span class="pred-record-pct">{pct:.1f}%</span>'
        )
    else:
        val = '<span class="pred-record">N/A</span>'

    return (
        f'<div class="pred-side">{logo_html}'
        f'<span class="pred-team">{label}</span>'
        f'{val}</div>'
    )


# ── Comparison bars ──────────────────────────────────────────────────────


def _build_bar_row(
    label: str, home_val: float, away_val: float, lower_is_better: bool = False,
) -> str:
    """Build a dual-direction horizontal comparison bar."""
    total = home_val + away_val
    if total == 0:
        home_pct = 50.0
    else:
        home_pct = (home_val / total) * 100
    away_pct = 100 - home_pct

    if lower_is_better:
        home_adv = " advantage" if home_val < away_val else ""
        away_adv = " advantage" if away_val < home_val else ""
    else:
        home_adv = " advantage" if home_val > away_val else ""
        away_adv = " advantage" if away_val > home_val else ""

    return (
        f'<div class="pred-bar-row">'
        f'<span class="pred-bar-label">{label}</span>'
        f'<div class="pred-bar-container">'
        f'<div class="pred-bar-left{home_adv}" style="width:{home_pct:.1f}%">{home_val:.1f}</div>'
        f'<div class="pred-bar-right{away_adv}" style="width:{away_pct:.1f}%">{away_val:.1f}</div>'
        f"</div></div>"
    )


# ── Edge callout ─────────────────────────────────────────────────────────


def _build_edge_callout(feat: dict, feat_label: str, market_key: str) -> str:
    """Build the matchup edge callout box."""
    ev = _safe_float(feat.get("EXPECTED_VALUE"))
    prob = _safe_float(feat.get("COVER_PROBABILITY"))

    if ev is not None and ev >= 0.05:
        icon, title = "\u2728", "Value Detected"
        text = f"{feat_label} shows +{ev * 100:.1f}% expected value \u2014 the model sees an edge here."
    elif ev is not None and ev >= 0.02:
        icon, title = "\U0001F4CA", "Slight Edge"
        text = f"{feat_label} has a marginal +{ev * 100:.1f}% EV. Small but positive edge."
    elif prob is not None and prob >= 0.55:
        icon, title = "\U0001F4CA", "Strong Cover Rate"
        text = f"{feat_label} covers at {prob * 100:.1f}% historically in similar spots."
    elif ev is not None and ev < 0:
        icon, title = "\u26A0\uFE0F", "Market Efficient"
        text = f"Negative EV ({ev * 100:.1f}%) suggests the market has this priced correctly."
    else:
        icon, title = "\U0001F4CA", "Market Analysis"
        text = "Market appears efficiently priced for this matchup."

    return (
        f'<div class="pred-edge">'
        f'<span class="pred-edge-icon">{icon}</span>'
        f'<div class="pred-edge-body">'
        f'<div class="pred-edge-title">{title}</div>'
        f'<div class="pred-edge-text">{text}</div>'
        f"</div></div>"
    )


# ── Prediction vs Result (Final games) ───────────────────────────────────


def _build_result_section(
    game: dict, feat: dict, feat_label: str, market_key: str,
) -> str:
    """Build prediction vs actual result comparison for Final games."""
    home_score = int(game.get("HOME_TEAM_SCORE") or 0)
    away_score = int(game.get("VISITOR_TEAM_SCORE") or 0)
    total_pts = home_score + away_score

    proj_home = _safe_float(feat.get("PROJECTED_HOME_SCORE"))
    proj_away = _safe_float(feat.get("PROJECTED_AWAY_SCORE"))
    proj_total = _safe_float(feat.get("PROJECTED_TOTAL"))

    cover = _compute_cover_result(game, feat, market_key)
    badge = f'<span class="pred-badge {cover.lower()}">{cover}</span>' if cover else ""

    home_abbr = get_team_abbrev(game["HOME_TEAM_NAME"])
    away_abbr = get_team_abbrev(game["VISITOR_TEAM_NAME"])

    if market_key == "totals":
        proj_disp = f"{proj_total:.1f}" if proj_total is not None else "N/A"
        actual_disp = str(total_pts)
        proj_label, actual_label = "Projected Total", "Actual Total"
        if proj_total is not None:
            diff = total_pts - proj_total
            sign = "+" if diff > 0 else ""
            cls = "positive" if diff > 0 else "negative" if diff < 0 else ""
            diff_disp = f'<span class="pred-result-value {cls}">{sign}{diff:.1f}</span>'
        else:
            diff_disp = '<span class="pred-result-value">N/A</span>'
    else:
        if proj_home is not None and proj_away is not None:
            proj_disp = f"{away_abbr} {proj_away:.0f} - {proj_home:.0f} {home_abbr}"
            d_away = away_score - proj_away
            d_home = home_score - proj_home
            s_away = "+" if d_away > 0 else ""
            s_home = "+" if d_home > 0 else ""
            c_away = "positive" if d_away > 0 else "negative" if d_away < 0 else ""
            c_home = "positive" if d_home > 0 else "negative" if d_home < 0 else ""
            diff_disp = (
                f'<span class="pred-result-value">'
                f'{away_abbr} <span class="{c_away}">{s_away}{d_away:.0f}</span>'
                f' &nbsp;|&nbsp; '
                f'{home_abbr} <span class="{c_home}">{s_home}{d_home:.0f}</span>'
                f'</span>'
            )
        else:
            proj_disp = "N/A"
            diff_disp = '<span class="pred-result-value">N/A</span>'
        actual_disp = f"{away_abbr} {away_score} - {home_score} {home_abbr}"
        proj_label, actual_label = "Projected Score", "Actual Score"

    return (
        f'<div class="pred-result">'
        f'<div class="pred-result-title">Prediction vs Result {badge}</div>'
        f'<div class="pred-result-grid">'
        f'<div class="pred-result-box">'
        f'<div class="pred-result-label">{proj_label}</div>'
        f'<div class="pred-result-value">{proj_disp}</div></div>'
        f'<div class="pred-result-box">'
        f'<div class="pred-result-label">{actual_label}</div>'
        f'<div class="pred-result-value">{actual_disp}</div></div>'
        f'<div class="pred-result-box">'
        f'<div class="pred-result-label">Difference</div>'
        f'{diff_disp}</div>'
        f"</div></div>"
    )


def _compute_cover_result(game: dict, feat: dict, market_key: str) -> str | None:
    """Compute COVERED/MISSED/PUSH for a Final game from scores + line."""
    if game.get("STATUS") != "Final":
        return None
    home_score = int(game.get("HOME_TEAM_SCORE") or 0)
    away_score = int(game.get("VISITOR_TEAM_SCORE") or 0)
    margin = home_score - away_score
    total = home_score + away_score
    side = feat.get("SIDE")
    home = game["HOME_TEAM_NAME"]

    if market_key == "spreads":
        line = _safe_float(feat.get("CONSENSUS_LINE"))
        if line is None:
            return None
        val = (margin + line) if side == home else (-margin + line)
        if val > 0:
            return "COVERED"
        return "PUSH" if val == 0 else "MISSED"

    if market_key == "h2h":
        if side == home:
            return "COVERED" if margin > 0 else "MISSED"
        return "COVERED" if margin < 0 else "MISSED"

    # totals
    line = _safe_float(feat.get("CONSENSUS_LINE"))
    if line is None:
        return None
    if side == "Over":
        diff = total - line
    else:
        diff = line - total
    if diff > 0:
        return "COVERED"
    return "PUSH" if diff == 0 else "MISSED"


# ── Prediction helpers ───────────────────────────────────────────────────


def _feat_label_html(label: str, logo_url: str) -> str:
    """Render featured team label with optional logo."""
    if logo_url:
        return (
            f'<span class="pred-feat-label">'
            f'<img src="{logo_url}" class="pred-feat-logo">'
            f'{label}</span>'
        )
    return f'<span class="pred-feat-label">{label}</span>'


def _is_missing(val) -> bool:
    """Check if a value is None or NaN (from LEFT JOIN)."""
    if val is None:
        return True
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _safe_float(val, default=None):
    """Convert to float, returning *default* if missing/NaN."""
    if _is_missing(val):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _fmt_price(price) -> str:
    """Format American odds price (+150 / -110)."""
    if _is_missing(price):
        return "N/A"
    p = int(float(price))
    return f"+{p}" if p > 0 else str(p)


def _fmt_line(line) -> str:
    """Format a spread / total line (+6, -4.5, 224.5)."""
    if _is_missing(line):
        return "N/A"
    val = float(line)
    sign = "+" if val > 0 else ""
    return f"{sign}{val:g}"


def _market_record_label(market_key: str) -> str:
    """Return short label for the market record type."""
    return {"spreads": "ATS", "h2h": "SU", "totals": "O/U"}.get(market_key, "")


# ── Stats tab ────────────────────────────────────────────────────────────


def render_stats_tab(game: dict):
    """Render Stats tab: live odds, team stats comparison, player box scores."""
    game_id = int(game["GAME_ID"])
    game_date = game["GAME_DATE"]
    home = game["HOME_TEAM_NAME"]
    away = game["VISITOR_TEAM_NAME"]
    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)

    _render_odds_section(game_date, home, away, home_abbr, away_abbr, home_logo, away_logo)
    _render_team_stats_section(game_id, away, home, away_abbr, home_abbr, away_logo, home_logo)
    _render_player_box_scores_section(game_id, home, away, home_abbr, away_abbr, home_logo, away_logo)


# ── Section 1: Live Betting Odds ─────────────────────────────────────────


def _render_odds_section(
    game_date, home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
):
    """Render live betting odds table for the game."""
    odds_df = get_live_odds_for_game(game_date, home)

    if odds_df.empty:
        st.markdown(
            '<div class="stats-section">'
            '<div class="stats-section-title">Betting Odds</div>'
            '<div class="stats-empty">No odds available for this game</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    # Prefer DraftKings, fall back to FanDuel, then first available
    bookmakers = odds_df["BOOKMAKER_KEY"].unique()
    if "draftkings" in bookmakers:
        bk = "draftkings"
    elif "fanduel" in bookmakers:
        bk = "fanduel"
    else:
        bk = bookmakers[0]

    bk_df = odds_df[odds_df["BOOKMAKER_KEY"] == bk]
    bk_title = bk_df.iloc[0]["BOOKMAKER_TITLE"] if not bk_df.empty else bk

    def _get_outcome(market: str, outcome_name: str):
        match = bk_df[
            (bk_df["MARKET_KEY"] == market) & (bk_df["OUTCOME_NAME"] == outcome_name)
        ]
        if match.empty:
            return None, None
        row = match.iloc[0]
        return _safe_float(row.get("OUTCOME_PRICE")), _safe_float(row.get("OUTCOME_POINT"))

    # Away team odds
    away_spread_price, away_spread_point = _get_outcome("spreads", away)
    away_ml_price, _ = _get_outcome("h2h", away)
    away_total_price, away_total_point = _get_outcome("totals", "Over")

    # Home team odds
    home_spread_price, home_spread_point = _get_outcome("spreads", home)
    home_ml_price, _ = _get_outcome("h2h", home)
    home_total_price, home_total_point = _get_outcome("totals", "Under")

    def _spread_cell(point, price):
        if point is None or price is None:
            return '<span class="odds-cell-na">--</span>'
        sign = "+" if point > 0 else ""
        return f'{sign}{point:g} <span class="odds-cell-price">{_fmt_price(price)}</span>'

    def _total_cell(label, point, price):
        if point is None or price is None:
            return '<span class="odds-cell-na">--</span>'
        return f'{label}{point:g} <span class="odds-cell-price">{_fmt_price(price)}</span>'

    def _ml_cell(price):
        if price is None:
            return '<span class="odds-cell-na">--</span>'
        return _fmt_price(price)

    html = (
        f'<div class="stats-section" style="margin-top:0;padding-top:0;border-top:none;">'
        f'<div class="stats-section-title">Betting Odds</div>'
        f'<div class="odds-table">'
        f'<div class="odds-table-header">'
        f'<span class="odds-col-team">Team</span>'
        f'<span class="odds-col">Spread</span>'
        f'<span class="odds-col">Total</span>'
        f'<span class="odds-col">Moneyline</span>'
        f'</div>'
        f'<div class="odds-table-row">'
        f'<span class="odds-col-team">'
        f'<img src="{away_logo}" class="odds-team-logo">'
        f'<span class="odds-team-abbr">{away_abbr}</span>'
        f'</span>'
        f'<span class="odds-col">{_spread_cell(away_spread_point, away_spread_price)}</span>'
        f'<span class="odds-col">{_total_cell("O", away_total_point, away_total_price)}</span>'
        f'<span class="odds-col">{_ml_cell(away_ml_price)}</span>'
        f'</div>'
        f'<div class="odds-table-row">'
        f'<span class="odds-col-team">'
        f'<img src="{home_logo}" class="odds-team-logo">'
        f'<span class="odds-team-abbr">{home_abbr}</span>'
        f'</span>'
        f'<span class="odds-col">{_spread_cell(home_spread_point, home_spread_price)}</span>'
        f'<span class="odds-col">{_total_cell("U", home_total_point, home_total_price)}</span>'
        f'<span class="odds-col">{_ml_cell(home_ml_price)}</span>'
        f'</div>'
        f'<div class="odds-source">Odds provided by {bk_title}</div>'
        f'</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ── Section 2: Live Team Stats ───────────────────────────────────────────


def _render_team_stats_section(
    game_id: int,
    away: str, home: str,
    away_abbr: str, home_abbr: str,
    away_logo: str, home_logo: str,
):
    """Render live team stats comparison bars (reuses matchup bar components)."""
    team_df = get_team_box_score_for_game(game_id)

    if team_df.empty:
        st.markdown(
            '<div class="stats-section">'
            '<div class="stats-section-title">Team Stats</div>'
            '<div class="stats-empty">No team stats available yet</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    away_row = team_df[team_df["IS_HOME"] == False]  # noqa: E712
    home_row = team_df[team_df["IS_HOME"] == True]  # noqa: E712
    if away_row.empty or home_row.empty:
        st.markdown(
            '<div class="stats-section">'
            '<div class="stats-section-title">Team Stats</div>'
            '<div class="stats-empty">Waiting for game data...</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    a = away_row.iloc[0].to_dict()
    h = home_row.iloc[0].to_dict()

    parts: list[str] = ['<div class="mu-section" style="margin-top:0;padding-top:0;border-top:none;">']
    parts.append(_build_matchup_header("Team Stats", away_abbr, home_abbr, away_logo, home_logo))

    def _live_row(label: str, col: str, fmt: str = "d", lower_is_better: bool = False):
        av = _safe_float(a.get(col))
        hv = _safe_float(h.get(col))
        if av is None or hv is None:
            return ""
        if fmt == "d":
            a_disp, h_disp = str(int(av)), str(int(hv))
        elif fmt == "pct":
            a_disp = f"{av * 100:.1f}%" if av <= 1 else f"{av:.1f}%"
            h_disp = f"{hv * 100:.1f}%" if hv <= 1 else f"{hv:.1f}%"
        else:
            a_disp, h_disp = f"{av:{fmt}}", f"{hv:{fmt}}"
        if lower_is_better:
            ab, hb = av < hv, hv < av
        else:
            ab, hb = av > hv, hv > av
        return _build_matchup_row(
            label, a_disp, h_disp, away_better=ab, home_better=hb,
            away_num=av, home_num=hv, lower_is_better=lower_is_better,
        )

    parts.append(_live_row("Field Goal %", "FG_PCT", "pct"))
    parts.append(_live_row("Free Throw %", "FT_PCT", "pct"))
    parts.append(_live_row("Three Point %", "FG3_PCT", "pct"))
    parts.append(_live_row("Assists", "AST"))
    parts.append(_live_row("Rebounds", "REB"))
    parts.append(_live_row("Def. Rebounds", "DREB"))
    parts.append(_live_row("Off. Rebounds", "OREB"))
    parts.append(_live_row("Steals", "STL"))
    parts.append(_live_row("Blocks", "BLK"))
    parts.append(_live_row("Fouls", "PF", lower_is_better=True))
    parts.append(_live_row("Turnovers", "TURNOVERS", lower_is_better=True))

    parts.append("</div>")
    st.markdown("\n".join(parts), unsafe_allow_html=True)


# ── Section 3: Player Box Scores ─────────────────────────────────────────


def _render_player_box_scores_section(
    game_id: int,
    home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
):
    """Render player box score tables for both teams (home first, then away)."""
    box_df = get_box_score_for_game(game_id)

    if box_df.empty:
        st.markdown(
            '<div class="stats-section">'
            '<div class="stats-section-title">Player Stats</div>'
            '<div class="stats-empty">No player stats available yet</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    home_df = box_df[box_df["IS_HOME"] == True].copy()  # noqa: E712
    away_df = box_df[box_df["IS_HOME"] == False].copy()  # noqa: E712

    home_html = _build_player_table(home_df, home, home_abbr, home_logo) if not home_df.empty else ""
    away_html = _build_player_table(away_df, away, away_abbr, away_logo) if not away_df.empty else ""

    if home_html or away_html:
        st.markdown(
            f'<div class="box-grid">'
            f'<div>{away_html}</div>'
            f'<div>{home_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _build_player_table(
    team_df: pd.DataFrame, team_name: str, abbr: str, logo: str,
) -> str:
    """Build HTML table for one team's player box scores."""
    team_df = team_df.copy()
    team_df["MIN_SORT"] = team_df["MIN"].apply(_parse_minutes)
    team_df = team_df.sort_values("MIN_SORT", ascending=False)

    # Top 5 by minutes = Starters, rest = Bench
    played = team_df[team_df["MIN_SORT"] > 0]
    not_played = team_df[team_df["MIN_SORT"] == 0]
    if len(played) > 5:
        starters = played.head(5)
        bench = pd.concat([played.tail(len(played) - 5), not_played])
    else:
        starters = played
        bench = not_played

    total_pts = int(team_df["PTS"].fillna(0).sum())

    parts = []
    parts.append(
        f'<div class="box-team-header">'
        f'<img src="{logo}" class="box-team-logo">'
        f'<span class="box-team-name">{team_name}</span>'
        f'<span class="box-team-pts">{total_pts}</span>'
        f'</div>'
    )

    # Column headers
    parts.append(
        '<div class="box-row box-col-header">'
        '<span class="box-player-col"></span>'
        '<span class="box-stat-col">MIN</span>'
        '<span class="box-stat-col">PTS</span>'
        '<span class="box-stat-col">REB</span>'
        '<span class="box-stat-col">AST</span>'
        '<span class="box-stat-col">STL</span>'
        '<span class="box-stat-col">BLK</span>'
        '<span class="box-stat-col">TO</span>'
        '</div>'
    )

    if not starters.empty:
        parts.append('<div class="box-group-label">Starters</div>')
        for _, player in starters.iterrows():
            parts.append(_build_player_row(player))

    if not bench.empty:
        parts.append('<div class="box-group-label">Bench</div>')
        for _, player in bench.iterrows():
            parts.append(_build_player_row(player))

    return "\n".join(parts)


def _build_player_row(player: pd.Series) -> str:
    """Build HTML for a single player row in the box score table."""
    name = player.get("PLAYER_NAME") or ""
    name_parts = name.split()
    if len(name_parts) >= 2:
        short_name = f"{name_parts[0][0]}. {' '.join(name_parts[1:])}"
    else:
        short_name = name

    minutes = player.get("MIN") or ""
    if ":" in str(minutes):
        minutes = str(minutes).split(":")[0]

    pts = _int_or_dash(player.get("PTS"))
    reb = _int_or_dash(player.get("REB"))
    ast = _int_or_dash(player.get("AST"))
    stl = _int_or_dash(player.get("STL"))
    blk = _int_or_dash(player.get("BLK"))
    to = _int_or_dash(player.get("TURNOVER"))

    pts_val = _safe_float(player.get("PTS"), 0)
    pts_cls = " box-highlight" if pts_val >= 20 else ""

    return (
        f'<div class="box-row">'
        f'<span class="box-player-col">{short_name}</span>'
        f'<span class="box-stat-col box-min">{minutes}</span>'
        f'<span class="box-stat-col{pts_cls}">{pts}</span>'
        f'<span class="box-stat-col">{reb}</span>'
        f'<span class="box-stat-col">{ast}</span>'
        f'<span class="box-stat-col">{stl}</span>'
        f'<span class="box-stat-col">{blk}</span>'
        f'<span class="box-stat-col">{to}</span>'
        f'</div>'
    )


def _parse_minutes(min_str) -> float:
    """Parse MIN string ('34:22' or '34') to float minutes for sorting."""
    if min_str is None or str(min_str).strip() == "":
        return 0.0
    s = str(min_str).strip()
    if ":" in s:
        parts = s.split(":")
        try:
            return float(parts[0]) + float(parts[1]) / 60
        except (ValueError, IndexError):
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _int_or_dash(val) -> str:
    """Format an integer stat value, returning '-' for None/NaN/0."""
    if _is_missing(val):
        return "-"
    try:
        v = int(float(val))
        return str(v) if v > 0 else "-"
    except (TypeError, ValueError):
        return "-"
