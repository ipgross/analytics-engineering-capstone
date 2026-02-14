"""HTML rendering for predictions table and best bets strip."""

import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data.teams import get_logo_url, get_team_abbrev

EASTERN = ZoneInfo("America/New_York")


def _is_missing(val) -> bool:
    """Check if a value is None or NaN."""
    if val is None:
        return True
    try:
        return math.isnan(float(val))
    except (TypeError, ValueError):
        return False


def _fmt_price(price) -> str:
    """Format American odds price."""
    if _is_missing(price):
        return "—"
    p = int(float(price))
    return f"+{p}" if p > 0 else str(p)


def _fmt_spread(line, price=None) -> str:
    """Format spread line with optional price."""
    if _is_missing(line):
        return "—"
    val = float(line)
    sign = "+" if val > 0 else ""
    spread_str = f"{sign}{val:g}"
    if price is not None and not _is_missing(price):
        spread_str += f" ({_fmt_price(price)})"
    return spread_str


def _fmt_ev(ev) -> tuple[str, str]:
    """Format expected value and return (text, css_class)."""
    if _is_missing(ev):
        return "—", "ev-neutral"
    val = float(ev) * 100  # Convert to percentage
    if val >= 0:
        return f"+{val:.1f}%", "ev-positive"
    return f"{val:.1f}%", "ev-negative"


def _fmt_stars(rating) -> str:
    """Format star rating as filled/empty stars."""
    if _is_missing(rating):
        return ""
    r = int(float(rating))
    return "★" * r + "☆" * (5 - r)


def _fmt_time(game_datetime) -> str:
    """Format game time in ET."""
    if game_datetime is None:
        return "TBD"
    if isinstance(game_datetime, str):
        utc_dt = datetime.fromisoformat(game_datetime).replace(tzinfo=timezone.utc)
    else:
        utc_dt = game_datetime.replace(tzinfo=timezone.utc)
    et_dt = utc_dt.astimezone(EASTERN)
    return et_dt.strftime("%I:%M %p").lstrip("0")


def _get_best_bet_label(game: dict) -> str:
    """Get the best bet market label for a game."""
    market = game.get("BEST_MARKET", "")
    if market == "spreads":
        return "Spread"
    if market == "h2h":
        return "ML"
    if market == "totals":
        return "Total"
    return ""


def render_best_bets_strip(bets_df) -> str:
    """Render the horizontal best bets strip (top 3 by EV)."""
    if bets_df.empty:
        return ""

    tiles = []
    for _, bet in bets_df.head(3).iterrows():
        home = bet.get("HOME_TEAM", "")
        away = bet.get("AWAY_TEAM", "")
        market = bet.get("MARKET_KEY", "")
        side = bet.get("SIDE", "")
        line = bet.get("CONSENSUS_LINE")
        ev = bet.get("EXPECTED_VALUE")
        rating = bet.get("BET_RATING")

        ev_text, ev_class = _fmt_ev(ev)
        stars = _fmt_stars(rating)

        # Build pick label
        if market == "spreads":
            pick_label = f"{get_team_abbrev(side)} {_fmt_spread(line)}"
        elif market == "h2h":
            pick_label = f"{get_team_abbrev(side)} ML"
        elif market == "totals":
            pick_label = f"{side} {float(line):g}" if not _is_missing(line) else side
        else:
            pick_label = side

        # Matchup
        matchup = f"{get_team_abbrev(away)} @ {get_team_abbrev(home)}"

        tiles.append(f"""
        <div class="best-bet-tile">
            <div class="best-bet-matchup">{matchup}</div>
            <div class="best-bet-pick">{pick_label}</div>
            <div class="best-bet-stars">{stars}</div>
            <div class="best-bet-ev {ev_class}">{ev_text}</div>
        </div>
        """)

    return f"""
    <div class="best-bets-strip">
        <div class="best-bets-header">BEST BETS</div>
        <div class="best-bets-tiles">
            {''.join(tiles)}
        </div>
    </div>
    """


def render_predictions_table(df, show_live: bool = True) -> str:
    """Render the main predictions table as HTML.

    Args:
        df: DataFrame with predictions (all markets pivoted).
        show_live: Whether to show live status indicator.
    """
    if df.empty:
        return '<div class="pred-empty">No predictions available</div>'

    rows = []
    for _, game in df.iterrows():
        rows.append(_render_table_row(game, show_live))

    return f"""
    <div class="pred-table-wrap">
        <table class="pred-table">
            <thead>
                <tr>
                    <th class="pred-th-time">Time</th>
                    <th class="pred-th-matchup">Matchup</th>
                    <th class="pred-th-spread">Spread</th>
                    <th class="pred-th-ev">EV</th>
                    <th class="pred-th-ml">Moneyline</th>
                    <th class="pred-th-total">Total</th>
                    <th class="pred-th-ev">EV</th>
                    <th class="pred-th-proj">Proj</th>
                    <th class="pred-th-best">Best Bet</th>
                </tr>
            </thead>
            <tbody>
                {''.join(rows)}
            </tbody>
        </table>
    </div>
    """


def _render_table_row(game: dict, show_live: bool) -> str:
    """Render a single table row for a game."""
    # Status
    period = int(game.get("PERIOD") or 0)
    status = game.get("STATUS") or ""
    is_live = period > 0 and status != "Final"

    # Time cell
    if is_live:
        clock = game.get("CLOCK") or ""
        if ":" in clock:
            parts = clock.split()
            clock = parts[-1] if len(parts) > 1 else clock
        time_html = f'<span class="pred-live-indicator"><span class="live-dot"></span>{status}</span>'
    else:
        time_html = _fmt_time(game.get("GAME_DATETIME"))

    # Teams
    home = game.get("HOME_TEAM_NAME", "")
    away = game.get("VISITOR_TEAM_NAME", "")
    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    away_logo = get_logo_url(away, 500)
    home_logo = get_logo_url(home, 500)

    matchup_html = f"""
    <div class="pred-matchup">
        <img src="{away_logo}" class="pred-team-logo" alt="">
        <span class="pred-team-abbr">{away_abbr}</span>
        <span class="pred-at">@</span>
        <img src="{home_logo}" class="pred-team-logo" alt="">
        <span class="pred-team-abbr">{home_abbr}</span>
    </div>
    """

    # Spread cell (show home team spread)
    spread_line = game.get("SPREAD_HOME_LINE")
    spread_price = game.get("SPREAD_HOME_PRICE")
    if not _is_missing(spread_line):
        spread_val = float(spread_line)
        # Show favorite's spread
        if spread_val > 0:
            # Away is favorite
            away_line = game.get("SPREAD_AWAY_LINE")
            away_price = game.get("SPREAD_AWAY_PRICE")
            spread_html = f'{away_abbr} {_fmt_spread(away_line)} <span class="pred-price">{_fmt_price(away_price)}</span>'
        else:
            spread_html = f'{home_abbr} {_fmt_spread(spread_line)} <span class="pred-price">{_fmt_price(spread_price)}</span>'
    else:
        spread_html = "—"

    # Spread EV
    spread_ev = game.get("SPREAD_HOME_EV")
    away_spread_ev = game.get("SPREAD_AWAY_EV")
    # Use the better EV
    if not _is_missing(spread_ev) and not _is_missing(away_spread_ev):
        if float(away_spread_ev) > float(spread_ev):
            spread_ev = away_spread_ev
    spread_ev_text, spread_ev_class = _fmt_ev(spread_ev)

    # Moneyline cell
    ml_home = game.get("ML_HOME_PRICE")
    ml_away = game.get("ML_AWAY_PRICE")
    if not _is_missing(ml_home) and not _is_missing(ml_away):
        ml_html = f'{_fmt_price(ml_away)} / {_fmt_price(ml_home)}'
    else:
        ml_html = "—"

    # Total cell
    total_line = game.get("TOTAL_LINE")
    over_price = game.get("OVER_PRICE")
    if not _is_missing(total_line):
        total_html = f'O {float(total_line):g} <span class="pred-price">{_fmt_price(over_price)}</span>'
    else:
        total_html = "—"

    # Total EV
    over_ev = game.get("OVER_EV")
    under_ev = game.get("UNDER_EV")
    # Use the better EV
    if not _is_missing(over_ev) and not _is_missing(under_ev):
        if float(under_ev) > float(over_ev):
            over_ev = under_ev
    total_ev_text, total_ev_class = _fmt_ev(over_ev)

    # Projected score
    proj_home = game.get("PROJECTED_HOME_SCORE")
    proj_away = game.get("PROJECTED_AWAY_SCORE")
    if not _is_missing(proj_home) and not _is_missing(proj_away):
        proj_html = f'{int(float(proj_away))}-{int(float(proj_home))}'
    else:
        proj_html = "—"

    # Best bet
    best_rating = game.get("BEST_RATING")

    if not _is_missing(best_rating) and int(float(best_rating)) > 0:
        market_label = _get_best_bet_label(game)
        stars = _fmt_stars(best_rating)
        best_html = f'{market_label} <span class="pred-best-stars">{stars}</span>'
    else:
        best_html = "—"

    row_class = "pred-row pred-row-live" if is_live else "pred-row"

    return f"""
    <tr class="{row_class}">
        <td class="pred-td-time">{time_html}</td>
        <td class="pred-td-matchup">{matchup_html}</td>
        <td class="pred-td-spread">{spread_html}</td>
        <td class="pred-td-ev {spread_ev_class}">{spread_ev_text}</td>
        <td class="pred-td-ml">{ml_html}</td>
        <td class="pred-td-total">{total_html}</td>
        <td class="pred-td-ev {total_ev_class}">{total_ev_text}</td>
        <td class="pred-td-proj">{proj_html}</td>
        <td class="pred-td-best">{best_html}</td>
    </tr>
    """


def render_game_detail_expansion(game: dict) -> str:
    """Render expanded detail view for a game (L10 stats comparison)."""
    home = game.get("HOME_TEAM_NAME", "")
    away = game.get("VISITOR_TEAM_NAME", "")
    home_abbr = get_team_abbrev(home)
    away_abbr = get_team_abbrev(away)
    home_logo = get_logo_url(home, 500)
    away_logo = get_logo_url(away, 500)

    # L10 stats
    home_pts = game.get("HOME_L10_PTS")
    away_pts = game.get("AWAY_L10_PTS")
    home_off = game.get("HOME_L10_OFF_RATING")
    away_off = game.get("AWAY_L10_OFF_RATING")
    home_def = game.get("HOME_L10_DEF_RATING")
    away_def = game.get("AWAY_L10_DEF_RATING")

    def _fmt_stat(val, decimals=1):
        if _is_missing(val):
            return "—"
        return f"{float(val):.{decimals}f}"

    def _advantage_class(val1, val2, higher_better=True):
        """Return CSS class for the better value."""
        if _is_missing(val1) or _is_missing(val2):
            return "", ""
        v1, v2 = float(val1), float(val2)
        if higher_better:
            if v1 > v2:
                return "pred-advantage", ""
            elif v2 > v1:
                return "", "pred-advantage"
        else:
            if v1 < v2:
                return "pred-advantage", ""
            elif v2 < v1:
                return "", "pred-advantage"
        return "", ""

    pts_away_cls, pts_home_cls = _advantage_class(away_pts, home_pts)
    off_away_cls, off_home_cls = _advantage_class(away_off, home_off)
    def_away_cls, def_home_cls = _advantage_class(away_def, home_def, higher_better=False)

    return f"""
    <div class="pred-detail">
        <div class="pred-detail-header">
            <div class="pred-detail-team">
                <img src="{away_logo}" class="pred-detail-logo" alt="">
                <span>{away_abbr}</span>
            </div>
            <span class="pred-detail-title">L10 COMPARISON</span>
            <div class="pred-detail-team">
                <span>{home_abbr}</span>
                <img src="{home_logo}" class="pred-detail-logo" alt="">
            </div>
        </div>
        <div class="pred-detail-row">
            <span class="pred-detail-val {pts_away_cls}">{_fmt_stat(away_pts, 1)}</span>
            <span class="pred-detail-label">PPG</span>
            <span class="pred-detail-val {pts_home_cls}">{_fmt_stat(home_pts, 1)}</span>
        </div>
        <div class="pred-detail-row">
            <span class="pred-detail-val {off_away_cls}">{_fmt_stat(away_off, 1)}</span>
            <span class="pred-detail-label">Off Rtg</span>
            <span class="pred-detail-val {off_home_cls}">{_fmt_stat(home_off, 1)}</span>
        </div>
        <div class="pred-detail-row">
            <span class="pred-detail-val {def_away_cls}">{_fmt_stat(away_def, 1)}</span>
            <span class="pred-detail-label">Def Rtg</span>
            <span class="pred-detail-val {def_home_cls}">{_fmt_stat(home_def, 1)}</span>
        </div>
    </div>
    """
