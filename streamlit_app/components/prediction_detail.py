"""Full prediction detail panel showing all markets without toggle.

Uses pivoted data from the game dict (no separate Snowflake query).
"""

import math
import streamlit as st

from data.teams import get_logo_url, get_team_abbrev


def _is_missing(val) -> bool:
    """Check if a value is None or NaN."""
    if val is None:
        return True
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _safe_float(val, default=None):
    """Convert to float, returning default if missing/NaN."""
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


def _extract_market_data(game: dict) -> dict:
    """Extract per-market/side dicts from pivoted game dict.

    Returns dict with keys 'spreads', 'h2h', 'totals'. Each contains
    'side_a' and 'side_b' dicts with standardized keys.
    """
    home = game.get("HOME_TEAM_NAME", "")
    away = game.get("VISITOR_TEAM_NAME", "")
    markets = {}

    # Spreads
    if not _is_missing(game.get("SPREAD_HOME_LINE")):
        markets["spreads"] = {
            "side_a": {
                "SIDE": away,
                "CONSENSUS_LINE": game.get("SPREAD_AWAY_LINE"),
                "CONSENSUS_PRICE": game.get("SPREAD_AWAY_PRICE"),
                "COVER_PROBABILITY": game.get("SPREAD_AWAY_PROB"),
                "EXPECTED_VALUE": game.get("SPREAD_AWAY_EV"),
                "BET_RATING": game.get("SPREAD_AWAY_RATING"),
                "SEASON_MARKET_WINS": game.get("SPREAD_AWAY_SEASON_WINS"),
                "SEASON_MARKET_TOTAL": game.get("SPREAD_AWAY_SEASON_TOTAL"),
            },
            "side_b": {
                "SIDE": home,
                "CONSENSUS_LINE": game.get("SPREAD_HOME_LINE"),
                "CONSENSUS_PRICE": game.get("SPREAD_HOME_PRICE"),
                "COVER_PROBABILITY": game.get("SPREAD_HOME_PROB"),
                "EXPECTED_VALUE": game.get("SPREAD_HOME_EV"),
                "BET_RATING": game.get("SPREAD_HOME_RATING"),
                "SEASON_MARKET_WINS": game.get("SPREAD_HOME_SEASON_WINS"),
                "SEASON_MARKET_TOTAL": game.get("SPREAD_HOME_SEASON_TOTAL"),
            },
        }

    # Moneyline (h2h)
    if not _is_missing(game.get("ML_HOME_PRICE")):
        markets["h2h"] = {
            "side_a": {
                "SIDE": away,
                "CONSENSUS_PRICE": game.get("ML_AWAY_PRICE"),
                "COVER_PROBABILITY": game.get("ML_AWAY_PROB"),
                "EXPECTED_VALUE": game.get("ML_AWAY_EV"),
                "BET_RATING": game.get("ML_AWAY_RATING"),
                "SEASON_MARKET_WINS": game.get("ML_AWAY_SEASON_WINS"),
                "SEASON_MARKET_TOTAL": game.get("ML_AWAY_SEASON_TOTAL"),
            },
            "side_b": {
                "SIDE": home,
                "CONSENSUS_PRICE": game.get("ML_HOME_PRICE"),
                "COVER_PROBABILITY": game.get("ML_HOME_PROB"),
                "EXPECTED_VALUE": game.get("ML_HOME_EV"),
                "BET_RATING": game.get("ML_HOME_RATING"),
                "SEASON_MARKET_WINS": game.get("ML_HOME_SEASON_WINS"),
                "SEASON_MARKET_TOTAL": game.get("ML_HOME_SEASON_TOTAL"),
            },
        }

    # Totals
    if not _is_missing(game.get("TOTAL_LINE")):
        markets["totals"] = {
            "side_a": {
                "SIDE": "Over",
                "CONSENSUS_LINE": game.get("TOTAL_LINE"),
                "CONSENSUS_PRICE": game.get("OVER_PRICE"),
                "COVER_PROBABILITY": game.get("OVER_PROB"),
                "EXPECTED_VALUE": game.get("OVER_EV"),
                "BET_RATING": game.get("OVER_RATING"),
                "SEASON_MARKET_WINS": game.get("OVER_SEASON_WINS"),
                "SEASON_MARKET_TOTAL": game.get("OVER_SEASON_TOTAL"),
            },
            "side_b": {
                "SIDE": "Under",
                "CONSENSUS_LINE": game.get("TOTAL_LINE"),
                "CONSENSUS_PRICE": game.get("UNDER_PRICE"),
                "COVER_PROBABILITY": game.get("UNDER_PROB"),
                "EXPECTED_VALUE": game.get("UNDER_EV"),
                "BET_RATING": game.get("UNDER_RATING"),
                "SEASON_MARKET_WINS": game.get("UNDER_SEASON_WINS"),
                "SEASON_MARKET_TOTAL": game.get("UNDER_SEASON_TOTAL"),
            },
        }

    return markets


def render_all_markets_prediction(game: dict):
    """Render full prediction analysis showing ALL markets.

    Uses pivoted data from the game dict — no additional Snowflake query.
    """
    home = game.get("HOME_TEAM_NAME")
    away = game.get("VISITOR_TEAM_NAME")

    if not home or not away:
        st.info("No prediction data available for this game.")
        return

    markets = _extract_market_data(game)
    if not markets:
        st.info("No prediction data available for this game.")
        return

    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)

    is_final = game.get("STATUS") == "Final"
    period = int(game.get("PERIOD") or 0)
    is_live = period > 0 and not is_final

    parts: list[str] = []

    # ── Score Projection ──
    proj_home = _safe_float(game.get("PROJECTED_HOME_SCORE"))
    proj_away = _safe_float(game.get("PROJECTED_AWAY_SCORE"))
    proj_total = _safe_float(game.get("PROJECTED_TOTAL"))

    if proj_home is not None and proj_away is not None:
        margin = proj_home - proj_away
        home_win = " winner" if margin > 0 else ""
        away_win = " winner" if margin < 0 else ""
        fav_text = "Pick'em" if abs(margin) < 0.5 else f"{home_abbr if margin > 0 else away_abbr} favored by {abs(margin):.1f}"

        proj_html = (
            '<div class="pred-score-projection">'
            '<div class="pred-section-label">SCORE PROJECTION</div>'
            '<div class="pred-proj-matchup">'
            f'<div class="pred-proj-team"><img src="{away_logo}" class="pred-proj-logo"><span class="pred-proj-abbr">{away_abbr}</span><span class="pred-proj-score{away_win}">{proj_away:.0f}</span></div>'
            '<span class="pred-proj-sep">-</span>'
            f'<div class="pred-proj-team"><span class="pred-proj-score{home_win}">{proj_home:.0f}</span><span class="pred-proj-abbr">{home_abbr}</span><img src="{home_logo}" class="pred-proj-logo"></div>'
            '</div>'
            f'<div class="pred-proj-sub">Projected Total: {proj_total:.1f} pts &nbsp;|&nbsp; {fav_text}</div>'
            '</div>'
        )
        parts.append(proj_html)

    # ── Rest Days Banner ──
    home_rest = _safe_float(game.get("HOME_REST_DAYS"))
    away_rest = _safe_float(game.get("AWAY_REST_DAYS"))

    if home_rest is not None and away_rest is not None:
        home_rest_int = int(home_rest)
        away_rest_int = int(away_rest)
        parts.append(_build_rest_banner(
            away_abbr, away_rest_int, home_abbr, home_rest_int
        ))

    # ── Market sections ──
    parts.append('<div class="pred-markets-grid">')

    if "spreads" in markets:
        parts.append(_build_market_section(
            "SPREAD", markets["spreads"],
            home, away, home_abbr, away_abbr, home_logo, away_logo, "spreads"
        ))

    if "h2h" in markets:
        parts.append(_build_market_section(
            "MONEYLINE", markets["h2h"],
            home, away, home_abbr, away_abbr, home_logo, away_logo, "h2h"
        ))

    if "totals" in markets:
        parts.append(_build_market_section(
            "TOTAL", markets["totals"],
            home, away, home_abbr, away_abbr, home_logo, away_logo, "totals"
        ))

    parts.append('</div>')

    # ── L10 Team Comparison (matchup style) ──
    home_l10_pts = _safe_float(game.get("HOME_L10_PTS"))
    away_l10_pts = _safe_float(game.get("AWAY_L10_PTS"))
    home_l10_off = _safe_float(game.get("HOME_L10_OFF_RATING"))
    away_l10_off = _safe_float(game.get("AWAY_L10_OFF_RATING"))
    home_l10_def = _safe_float(game.get("HOME_L10_DEF_RATING"))
    away_l10_def = _safe_float(game.get("AWAY_L10_DEF_RATING"))

    if home_l10_pts is not None and away_l10_pts is not None:
        compare_html = (
            '<div class="mu-section">'
            '<div class="mu-header">'
            f'<div class="mu-team-badge">'
            f'<img src="{away_logo}" class="mu-team-logo">'
            f'<span class="mu-team-name">{away_abbr}</span></div>'
            '<span class="mu-section-title">L10 Comparison</span>'
            f'<div class="mu-team-badge">'
            f'<span class="mu-team-name">{home_abbr}</span>'
            f'<img src="{home_logo}" class="mu-team-logo"></div>'
            '</div>'
        )
        compare_html += _build_matchup_row("Points", away_l10_pts, home_l10_pts)
        if home_l10_off is not None and away_l10_off is not None:
            compare_html += _build_matchup_row("Off Rating", away_l10_off, home_l10_off)
        if home_l10_def is not None and away_l10_def is not None:
            compare_html += _build_matchup_row("Def Rating", away_l10_def, home_l10_def, lower_is_better=True)

        # ── Four Factors ──
        home_efg = _safe_float(game.get("HOME_L10_EFG_PCT"))
        away_efg = _safe_float(game.get("AWAY_L10_EFG_PCT"))
        home_tov = _safe_float(game.get("HOME_L10_TOV_PCT"))
        away_tov = _safe_float(game.get("AWAY_L10_TOV_PCT"))
        home_orb = _safe_float(game.get("HOME_L10_ORB_PCT"))
        away_orb = _safe_float(game.get("AWAY_L10_ORB_PCT"))
        home_ftr = _safe_float(game.get("HOME_L10_FTR"))
        away_ftr = _safe_float(game.get("AWAY_L10_FTR"))

        has_four_factors = (
            home_efg is not None and away_efg is not None
        )

        if has_four_factors:
            compare_html += '<div class="mu-sub-header">FOUR FACTORS</div>'
            compare_html += _build_matchup_row("eFG%", away_efg * 100, home_efg * 100)
            if home_tov is not None and away_tov is not None:
                compare_html += _build_matchup_row("TO%", away_tov * 100, home_tov * 100, lower_is_better=True)
            if home_orb is not None and away_orb is not None:
                compare_html += _build_matchup_row("ORB%", away_orb * 100, home_orb * 100)
            if home_ftr is not None and away_ftr is not None:
                compare_html += _build_matchup_row("FT Rate", away_ftr * 100, home_ftr * 100)

        # ── Pace ──
        home_pace = _safe_float(game.get("HOME_L10_POSSESSIONS"))
        away_pace = _safe_float(game.get("AWAY_L10_POSSESSIONS"))
        if home_pace is not None and away_pace is not None:
            if not has_four_factors:
                compare_html += '<div class="mu-sub-header">PACE</div>'
            compare_html += _build_matchup_row("Pace", away_pace, home_pace)

        compare_html += '</div>'
        parts.append(compare_html)

    # ── Live game note ──
    if is_live:
        parts.append('<div class="pred-live-note">Pre-game prediction — game is in progress</div>')

    st.markdown("\n".join(parts), unsafe_allow_html=True)


def _build_rest_banner(
    away_abbr: str, away_rest: int, home_abbr: str, home_rest: int,
) -> str:
    """Build rest days banner with B2B / well-rested indicators."""

    def _rest_label(days: int) -> str:
        if days <= 1:
            return "B2B"
        elif days == 2:
            return "1 Day Rest"
        elif days >= 4:
            return f"{days - 1} Days Rest"
        else:
            return f"{days - 1} Days Rest"

    def _rest_cls(days: int) -> str:
        if days <= 1:
            return " rest-b2b"
        elif days >= 4:
            return " rest-rested"
        return ""

    return (
        '<div class="pred-rest-bar">'
        f'<div class="pred-rest-team{_rest_cls(away_rest)}">'
        f'<span class="pred-rest-label">{away_abbr}</span>'
        f'<span class="pred-rest-value">{_rest_label(away_rest)}</span></div>'
        f'<div class="pred-rest-team{_rest_cls(home_rest)}">'
        f'<span class="pred-rest-label">{home_abbr}</span>'
        f'<span class="pred-rest-value">{_rest_label(home_rest)}</span></div>'
        '</div>'
    )


def _build_market_section(
    title: str,
    market_data: dict,
    home: str, away: str,
    home_abbr: str, away_abbr: str,
    home_logo: str, away_logo: str,
    market_key: str,
) -> str:
    """Build a market section (Spread, Moneyline, or Total).

    market_data has keys 'side_a' and 'side_b', each a dict with
    standardized column names (CONSENSUS_LINE, CONSENSUS_PRICE, etc.).
    """
    a = market_data["side_a"]
    b = market_data["side_b"]

    if market_key == "totals":
        label_a, label_b = "Over", "Under"
        logo_a, logo_b = "", ""
    else:
        label_a, label_b = away_abbr, home_abbr
        logo_a, logo_b = away_logo, home_logo

    # Featured side = higher bet rating
    rat_a = _safe_float(a.get("BET_RATING"), 0)
    rat_b = _safe_float(b.get("BET_RATING"), 0)
    if rat_a >= rat_b:
        feat, feat_label, feat_logo = a, label_a, logo_a
    else:
        feat, feat_label, feat_logo = b, label_b, logo_b

    html_parts = [f'<div class="pred-market-card"><div class="pred-market-title">{title}</div>']

    # Consensus line display
    logo_a_html = f'<img src="{logo_a}" class="pred-market-logo">' if logo_a else '<span class="pred-market-icon"></span>'
    logo_b_html = f'<img src="{logo_b}" class="pred-market-logo">' if logo_b else '<span class="pred-market-icon"></span>'

    if market_key == "h2h":
        disp_a = _fmt_price(a.get("CONSENSUS_PRICE"))
        disp_b = _fmt_price(b.get("CONSENSUS_PRICE"))
    else:
        line_a = _fmt_line(a.get("CONSENSUS_LINE"))
        line_b = _fmt_line(b.get("CONSENSUS_LINE"))
        price_a = _fmt_price(a.get("CONSENSUS_PRICE"))
        price_b = _fmt_price(b.get("CONSENSUS_PRICE"))
        disp_a = f"{line_a} ({price_a})"
        disp_b = f"{line_b} ({price_b})"

    html_parts.append(
        '<div class="pred-market-lines">'
        f'<div class="pred-market-side">{logo_a_html}<span class="pred-market-team">{label_a}</span><span class="pred-market-line">{disp_a}</span></div>'
        f'<div class="pred-market-side">{logo_b_html}<span class="pred-market-team">{label_b}</span><span class="pred-market-line">{disp_b}</span></div>'
        '</div>'
    )

    # Stats grid
    html_parts.append('<div class="pred-market-stats">')

    # Cover probability
    prob = _safe_float(feat.get("COVER_PROBABILITY"))
    if prob is not None:
        pct_val = prob * 100
        pct_str = f"{pct_val:.1f}%"
        bar_cls = "pred-stat-bar-fill strong" if prob >= 0.55 else "pred-stat-bar-fill"
    else:
        pct_val, pct_str, bar_cls = 0, "N/A", "pred-stat-bar-fill"

    html_parts.append(
        '<div class="pred-stat-row">'
        '<span class="pred-stat-label">Cover Prob</span>'
        f'<div class="pred-stat-value"><span class="pred-stat-num">{pct_str}</span>'
        f'<div class="pred-stat-bar"><div class="{bar_cls}" style="width:{pct_val:.1f}%"></div></div></div>'
        '</div>'
    )

    # Expected Value
    ev = _safe_float(feat.get("EXPECTED_VALUE"))
    if ev is not None:
        ev_pct = ev * 100
        ev_sign = "+" if ev_pct > 0 else ""
        ev_str = f"{ev_sign}{ev_pct:.1f}%"
        ev_cls = "positive" if ev >= 0 else "negative"
    else:
        ev_str, ev_cls = "N/A", ""

    html_parts.append(
        '<div class="pred-stat-row">'
        '<span class="pred-stat-label">Expected Value</span>'
        f'<span class="pred-stat-ev {ev_cls}">{ev_str}</span>'
        '</div>'
    )

    # Bet Rating
    rating = _safe_float(feat.get("BET_RATING"))
    if rating is not None:
        stars_int = int(rating)
        stars_html = '<span class="pred-stars">' + ("★" * stars_int) + ("☆" * (5 - stars_int)) + '</span>'
    else:
        stars_html = '<span class="pred-stars">☆☆☆☆☆</span>'

    html_parts.append(
        '<div class="pred-stat-row">'
        '<span class="pred-stat-label">Bet Rating</span>'
        f'{stars_html}'
        '</div>'
    )

    # Season Record
    wins = _safe_float(feat.get("SEASON_MARKET_WINS"))
    total = _safe_float(feat.get("SEASON_MARKET_TOTAL"))
    if wins is not None and total is not None and total > 0:
        w, t = int(wins), int(total)
        record_pct = w / t * 100
        record_str = f"{w}-{t - w} ({record_pct:.0f}%)"
    else:
        record_str = "N/A"

    feat_logo_html = f'<img src="{feat_logo}" class="pred-stat-logo">' if feat_logo else ""
    html_parts.append(
        '<div class="pred-stat-row">'
        '<span class="pred-stat-label">Season Record</span>'
        f'<span class="pred-stat-record">{feat_logo_html}{feat_label} {record_str}</span>'
        '</div>'
    )

    html_parts.append('</div>')  # close pred-market-stats

    # Edge callout
    html_parts.append(_build_compact_edge(feat))

    html_parts.append('</div>')  # close pred-market-card
    return "".join(html_parts)


def _build_compact_edge(feat: dict) -> str:
    """Build a compact edge indicator."""
    ev = _safe_float(feat.get("EXPECTED_VALUE"))
    prob = _safe_float(feat.get("COVER_PROBABILITY"))

    if ev is not None and ev >= 0.05:
        cls = "edge-positive"
        text = f"Value: +{ev * 100:.1f}% EV"
    elif ev is not None and ev >= 0.02:
        cls = "edge-slight"
        text = f"Slight edge: +{ev * 100:.1f}% EV"
    elif prob is not None and prob >= 0.55:
        cls = "edge-slight"
        text = f"Strong cover: {prob * 100:.0f}%"
    elif ev is not None and ev < 0:
        cls = "edge-negative"
        text = "Market efficient"
    else:
        cls = "edge-neutral"
        text = "Fair price"

    return f'<div class="pred-edge {cls}">{text}</div>'


def _build_matchup_row(label: str, away_val: float, home_val: float, lower_is_better: bool = False) -> str:
    """Build a matchup comparison row matching the Matchup tab style.

    Format: away_value | label + bar | home_value
    """
    # Calculate bar proportions
    total = abs(away_val) + abs(home_val)
    if total > 0:
        away_pct = (abs(away_val) / total) * 100
    else:
        away_pct = 50.0
    home_pct = 100 - away_pct

    # Determine which side has advantage
    if lower_is_better:
        away_better = away_val < home_val
        home_better = home_val < away_val
    else:
        away_better = away_val > home_val
        home_better = home_val > away_val

    away_cls = " mu-advantage" if away_better else ""
    home_cls = " mu-advantage" if home_better else ""
    away_bar_cls = " mu-advantage" if away_better else ""
    home_bar_cls = " mu-advantage" if home_better else ""

    return (
        f'<div class="mu-row">'
        f'<div class="mu-val mu-left{away_cls}">{away_val:.1f}</div>'
        f'<div class="mu-row-center">'
        f'<div class="mu-label">{label}</div>'
        f'<div class="mu-bar">'
        f'<div class="mu-bar-left{away_bar_cls}" style="width:{away_pct:.1f}%"></div>'
        f'<div class="mu-bar-right{home_bar_cls}" style="width:{home_pct:.1f}%"></div>'
        f'</div></div>'
        f'<div class="mu-val mu-right{home_cls}">{home_val:.1f}</div>'
        f'</div>'
    )
