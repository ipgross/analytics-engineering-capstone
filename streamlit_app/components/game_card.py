"""HTML rendering for individual game cards."""

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data.teams import get_logo_url, get_team_abbrev

EASTERN = ZoneInfo("America/New_York")


def render_final_card(game: dict, result: dict | None, market_key: str) -> str:
    """Render a FINAL game card with betting results.

    Args:
        game: Scoreboard row dict (UPPERCASE).
        result: Row from live_nba__game_results (UPPERCASE), or None.
        market_key: 'spreads', 'h2h', or 'totals'.
    """
    away = game["VISITOR_TEAM_NAME"]
    home = game["HOME_TEAM_NAME"]
    away_score = int(game.get("VISITOR_TEAM_SCORE") or 0)
    home_score = int(game.get("HOME_TEAM_SCORE") or 0)

    away_logo = get_logo_url(away, 500)
    home_logo = get_logo_url(home, 500)
    away_abbr = get_team_abbrev(away)
    home_abbr = get_team_abbrev(home)

    away_cls = "winner" if away_score > home_score else "loser"
    home_cls = "winner" if home_score > away_score else "loser"

    result_html = _render_result(result, market_key, home_abbr, away_abbr) if result else '<div class="odds-line">No results data</div>'

    return f"""<div class="game-card">
  <div class="team-row">
    <div class="team-info">
      <img class="team-logo" src="{away_logo}" alt="">
      <span class="team-abbrev">{away_abbr}</span>
      <span class="team-name">{away}</span>
    </div>
    <span class="team-score {away_cls}">{away_score}</span>
  </div>
  <div class="team-row">
    <div class="team-info">
      <img class="team-logo" src="{home_logo}" alt="">
      <span class="team-abbrev">{home_abbr}</span>
      <span class="team-name">{home}</span>
    </div>
    <span class="team-score {home_cls}">{home_score}</span>
  </div>
  <div class="game-status">FINAL</div>
  {result_html}
</div>"""


def _render_result(result: dict, market_key: str, home_abbr: str, away_abbr: str) -> str:
    """Render betting result line for a completed game."""
    if market_key == "spreads":
        home_spread = result.get("HOME_SPREAD")
        home_result = result.get("HOME_SPREAD_RESULT")
        away_spread = result.get("AWAY_SPREAD")
        away_result = result.get("AWAY_SPREAD_RESULT")
        if _is_missing(home_spread):
            return '<div class="odds-line">No spread data</div>'
        home_cls = _result_css(home_result)
        away_cls = _result_css(away_result)
        h_sign = "+" if float(home_spread) > 0 else ""
        a_sign = "+" if float(away_spread) > 0 else ""
        return (
            f'<div class="odds-line">'
            f'{away_abbr} <span class="{away_cls}">{a_sign}{away_spread} {away_result}</span>'
            f' &nbsp;|&nbsp; '
            f'{home_abbr} <span class="{home_cls}">{h_sign}{home_spread} {home_result}</span>'
            f'</div>'
        )

    if market_key == "h2h":
        home_ml = result.get("HOME_ML_PRICE")
        home_result_val = result.get("HOME_ML_RESULT")
        away_ml = result.get("AWAY_ML_PRICE")
        away_result_val = result.get("AWAY_ML_RESULT")
        if _is_missing(home_ml):
            return '<div class="odds-line">No moneyline data</div>'
        home_cls = _result_css(home_result_val)
        away_cls = _result_css(away_result_val)
        return (
            f'<div class="odds-line">'
            f'{away_abbr} <span class="{away_cls}">{_fmt_price(away_ml)} {away_result_val}</span>'
            f' &nbsp;|&nbsp; '
            f'{home_abbr} <span class="{home_cls}">{_fmt_price(home_ml)} {home_result_val}</span>'
            f'</div>'
        )

    # totals
    total_line = result.get("TOTAL_LINE")
    over_result_val = result.get("OVER_RESULT")
    total_pts = result.get("TOTAL_POINTS")
    if _is_missing(total_line):
        return '<div class="odds-line">No total data</div>'
    total_cls = _result_css(over_result_val)
    total_pts_str = f" ({int(float(total_pts))} pts)" if not _is_missing(total_pts) else ""
    return (
        f'<div class="odds-line">'
        f'O/U <span class="{total_cls}">{total_line} {over_result_val}</span>'
        f'{total_pts_str}'
        f'</div>'
    )


def _result_css(result_str) -> str:
    """Return CSS class based on COVERED/MISSED/PUSH."""
    if result_str == "COVERED":
        return "odds-value result-covered"
    if result_str == "MISSED":
        return "odds-value result-missed"
    return "odds-value"


def render_game_card(game: dict, market_key: str, game_type: str, show_date: bool = False) -> str:
    """Render a single game card as HTML.

    Args:
        game: Dict from DataFrame row (UPPERCASE Snowflake column names).
        market_key: 'spreads', 'h2h', or 'totals'.
        game_type: 'live', 'final', or 'upcoming'.
        show_date: If True, include the date in the status line (for upcoming multi-day views).
    """
    away = game["VISITOR_TEAM_NAME"]
    home = game["HOME_TEAM_NAME"]
    away_score = int(game.get("VISITOR_TEAM_SCORE") or 0)
    home_score = int(game.get("HOME_TEAM_SCORE") or 0)

    away_logo = get_logo_url(away, 500)
    home_logo = get_logo_url(home, 500)
    away_abbr = get_team_abbrev(away)
    home_abbr = get_team_abbrev(home)

    # Score display
    if game_type == "upcoming":
        away_score_html = ""
        home_score_html = ""
        away_cls = home_cls = ""
    elif game_type == "final":
        away_score_html = str(away_score)
        home_score_html = str(home_score)
        away_cls = "winner" if away_score > home_score else "loser"
        home_cls = "winner" if home_score > away_score else "loser"
    else:  # live
        away_score_html = str(away_score)
        home_score_html = str(home_score)
        away_cls = home_cls = ""

    status_html = _render_status(game, game_type, show_date=show_date)
    odds_html = _render_odds(game, market_key)
    star_html = _render_stars(game, market_key)
    card_cls = "game-card live" if game_type == "live" else "game-card"

    return f"""<div class="{card_cls}">
  <div class="team-row">
    <div class="team-info">
      <img class="team-logo" src="{away_logo}" alt="">
      <span class="team-abbrev">{away_abbr}</span>
      <span class="team-name">{away}</span>
    </div>
    <span class="team-score {away_cls}">{away_score_html}</span>
  </div>
  <div class="team-row">
    <div class="team-info">
      <img class="team-logo" src="{home_logo}" alt="">
      <span class="team-abbrev">{home_abbr}</span>
      <span class="team-name">{home}</span>
    </div>
    <span class="team-score {home_cls}">{home_score_html}</span>
  </div>
  {status_html}
  {odds_html}
  {star_html}
</div>"""


# ── Status line ─────────────────────────────────────────────────────────────

def _render_status(game: dict, game_type: str, show_date: bool = False) -> str:
    if game_type == "live":
        period = int(game.get("PERIOD") or 0)
        clock = game.get("CLOCK") or ""
        status = game.get("STATUS") or ""

        # BDL status can be "1st Qtr", "2nd Qtr", "Halftime", etc.
        # Use it directly if it's descriptive; only build from period if needed
        if "half" in status.lower():
            label = "HALF"
            clock = ""
        elif status and any(q in status for q in ["Qtr", "OT", "Quarter"]):
            # Status already has period info — use it directly
            label = status
            # Clock may have redundant quarter prefix like "Q4 4:28" — strip it
            if clock and ":" in clock:
                # Extract just the time portion (e.g., "Q4 4:28" -> "4:28")
                parts = clock.split()
                clock = parts[-1] if len(parts) > 1 else clock
            else:
                clock = ""
        elif period <= 4:
            label = f"Q{period}"
        else:
            label = f"OT{period - 4}"

        clock_display = f" {clock}" if clock else ""
        return (
            f'<div class="game-status live">'
            f'<span class="live-dot"></span>{label}{clock_display}'
            f'</div>'
        )

    if game_type == "final":
        return '<div class="game-status">FINAL</div>'

    # Upcoming — show tip-off time + countdown (optionally with date)
    return f'<div class="game-status">{_format_tipoff(game, show_date=show_date)}</div>'


def _format_tipoff(game: dict, show_date: bool = False) -> str:
    """Format upcoming game time as 'H:MM PM ET (in Xh Ym)'.

    Args:
        game: Game dict with GAME_DATETIME key.
        show_date: If True, prepend the date (e.g., 'Fri, Feb 14').
    """
    game_dt = game.get("GAME_DATETIME")
    if game_dt is None:
        return game.get("STATUS") or "TBD"

    # game_datetime is TIMESTAMP_NTZ stored as UTC
    if isinstance(game_dt, str):
        utc_dt = datetime.fromisoformat(game_dt).replace(tzinfo=timezone.utc)
    else:
        utc_dt = game_dt.replace(tzinfo=timezone.utc)

    et_dt = utc_dt.astimezone(EASTERN)
    # %I is zero-padded; strip leading zero for clean display (cross-platform)
    time_str = et_dt.strftime("%I:%M %p ET").lstrip("0")

    # Prepend date for multi-day upcoming views
    if show_date:
        try:
            date_str = et_dt.strftime("%a, %b %-d")
        except ValueError:
            date_str = et_dt.strftime("%a, %b %d").replace(" 0", " ")
        time_str = f"{date_str} \u00b7 {time_str}"

    diff_secs = (utc_dt - datetime.now(timezone.utc)).total_seconds()
    if diff_secs < 0:
        return f"{time_str}"

    total_mins = int(diff_secs / 60)
    if total_mins < 60:
        return f"{time_str} (in {total_mins}m)"
    hours = total_mins // 60
    mins = total_mins % 60
    # Use day + hour format for multi-day gaps
    if hours >= 24:
        days = hours // 24
        rem_hours = hours % 24
        return f"{time_str} (in {days}d {rem_hours}h)"
    return f"{time_str} (in {hours}h {mins}m)"


# ── Odds display ────────────────────────────────────────────────────────────

def _render_odds(game: dict, market_key: str) -> str:
    home_price = game.get("HOME_CONSENSUS_PRICE")
    away_price = game.get("AWAY_CONSENSUS_PRICE")

    if _is_missing(home_price) and _is_missing(away_price):
        return '<div class="odds-line">No odds available</div>'

    if market_key == "spreads":
        return _render_spread_odds(game)
    if market_key == "h2h":
        return _render_h2h_odds(game)
    return _render_total_odds(game)


def _render_spread_odds(game: dict) -> str:
    home_line = game.get("HOME_CONSENSUS_LINE")
    home_price = game.get("HOME_CONSENSUS_PRICE")
    away_line = game.get("AWAY_CONSENSUS_LINE")
    away_price = game.get("AWAY_CONSENSUS_PRICE")

    away_abbr = get_team_abbrev(game["VISITOR_TEAM_NAME"])
    home_abbr = get_team_abbrev(game["HOME_TEAM_NAME"])

    away_str = _fmt_spread(away_line, away_price)
    home_str = _fmt_spread(home_line, home_price)

    return (
        f'<div class="odds-line">'
        f'{away_abbr} <span class="odds-value">{away_str}</span>'
        f' &nbsp;|&nbsp; '
        f'{home_abbr} <span class="odds-value">{home_str}</span>'
        f'</div>'
    )


def _render_h2h_odds(game: dict) -> str:
    away_price = game.get("AWAY_CONSENSUS_PRICE")
    home_price = game.get("HOME_CONSENSUS_PRICE")

    away_abbr = get_team_abbrev(game["VISITOR_TEAM_NAME"])
    home_abbr = get_team_abbrev(game["HOME_TEAM_NAME"])

    return (
        f'<div class="odds-line">'
        f'{away_abbr} <span class="odds-value">{_fmt_price(away_price)}</span>'
        f' &nbsp;|&nbsp; '
        f'{home_abbr} <span class="odds-value">{_fmt_price(home_price)}</span>'
        f'</div>'
    )


def _render_total_odds(game: dict) -> str:
    over_line = game.get("HOME_CONSENSUS_LINE")  # Over side
    over_price = game.get("HOME_CONSENSUS_PRICE")
    under_price = game.get("AWAY_CONSENSUS_PRICE")

    if over_line is None:
        return '<div class="odds-line">No total available</div>'

    return (
        f'<div class="odds-line">'
        f'O/U <span class="odds-value">{over_line}</span> '
        f'({_fmt_price(over_price)} / {_fmt_price(under_price)})'
        f'</div>'
    )


def _is_missing(val) -> bool:
    """Check if a value is None or NaN (from LEFT JOIN)."""
    if val is None:
        return True
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _fmt_spread(line, price) -> str:
    if _is_missing(line):
        return "N/A"
    sign = "+" if float(line) > 0 else ""
    return f"{sign}{line} ({_fmt_price(price)})"


def _fmt_price(price) -> str:
    if _is_missing(price):
        return "N/A"
    p = int(float(price))
    return f"+{p}" if p > 0 else str(p)


# ── Star rating ─────────────────────────────────────────────────────────────

def _render_stars(game: dict, market_key: str) -> str:
    """Render 1-5 star bet rating + projected total for spreads/h2h."""
    rating = game.get("HOME_BET_RATING")
    if _is_missing(rating):
        return ""

    stars_int = int(float(rating))
    filled = "\u2605" * stars_int       # filled star
    empty = "\u2606" * (5 - stars_int)  # empty star

    extra = ""
    proj_total = game.get("PROJECTED_TOTAL")
    if not _is_missing(proj_total) and market_key == "totals":
        extra = f" &middot; Proj {float(proj_total):.1f}"

    proj_home = game.get("PROJECTED_HOME_SCORE")
    proj_away = game.get("PROJECTED_AWAY_SCORE")
    if not _is_missing(proj_home) and not _is_missing(proj_away) and market_key != "totals":
        extra = f" &middot; Proj {float(proj_away):.0f}-{float(proj_home):.0f}"

    return f'<div class="star-rating">{filled}{empty}{extra}</div>'
