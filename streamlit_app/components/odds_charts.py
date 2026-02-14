"""Plotly chart builders and HTML component renderers for the Odds page."""

import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data.teams import get_logo_url, get_team_abbrev
from queries.odds import fmt_price, fmt_line, fmt_prob, _is_missing

EASTERN = ZoneInfo("America/New_York")

# ── Theme constants (match styles/theme.py) ──────────────────────────────────

BG_DARK = "#0C0C0C"
BG_CARD = "#1A1A2E"
BORDER = "#2A2A3E"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#9CA3AF"
TEXT_DIMMED = "#6B7280"
ACCENT_NBA = "#1d428a"
ACCENT_LIVE = "#C8102E"
ODDS_ACCENT = "#8EC5FC"
GREEN = "#00A651"

# Bookmaker line colors for the movement chart
BOOKMAKER_COLORS = {
    "fanduel": "#1493FF",
    "draftkings": "#53D769",
    "betmgm": "#C8A951",
    "caesars": "#2CDDAB",
    "pointsbetus": "#F47B20",
    "betrivers": "#FF6B6B",
}

BOOKMAKER_DISPLAY = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "caesars": "Caesars",
    "pointsbetus": "PointsBet",
    "betrivers": "BetRivers",
}

BOOKMAKER_SHORT = {
    "fanduel": "FD",
    "draftkings": "DK",
    "betmgm": "MGM",
    "caesars": "CZR",
    "pointsbetus": "PB",
    "betrivers": "BR",
    "bovada": "BOV",
    "fanatics": "FAN",
    "lowvig": "LOW",
    "mybookieag": "MYB",
    "williamhill_us": "WH",
    "betonlineag": "BOL",
    "betus": "BET",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Line Movement Chart (Plotly)
# ═══════════════════════════════════════════════════════════════════════════════


def get_available_bookmakers(movement_df: pd.DataFrame) -> list[str]:
    """Return sorted list of bookmaker keys present in the movement data."""
    if movement_df.empty:
        return []
    return sorted(movement_df["BOOKMAKER_KEY"].unique().tolist())


def build_line_movement_chart(
    movement_df: pd.DataFrame,
    market_key: str,
    side: str,
    commence_time_utc=None,
    show_implied_prob: bool = False,
    selected_source: str = "consensus",
    is_final: bool = False,
) -> go.Figure:
    """Build a Plotly area chart showing odds movement over time.

    ESPN win-probability style: single filled area line, clean minimal design.
    Time range clipped to ~30 min pre-tipoff through end of data.

    Args:
        movement_df: All snapshots for one game from get_odds_movement().
        market_key: 'spreads', 'h2h', or 'totals'.
        side: Which side to chart (team name, 'Over', or 'Under').
        commence_time_utc: Tip-off timestamp for vertical marker.
        show_implied_prob: Show implied probability instead of raw values.
        selected_source: 'consensus' or a bookmaker key (e.g. 'fanduel').

    Returns:
        Plotly Figure ready for st.plotly_chart().
    """
    fig = go.Figure()

    # Filter to the selected side and market
    side_df = movement_df[
        (movement_df["MARKET_KEY"] == market_key)
        & (movement_df["SIDE"] == side)
    ].copy()

    if side_df.empty:
        return _empty_chart("No line movement data available")

    # ── Use BOOKMAKER_LAST_UPDATE as the time axis (it's UTC from the API) ──
    # This avoids Snowflake session timezone issues with SNAPSHOT_TIME.
    time_col = "BOOKMAKER_LAST_UPDATE"
    if time_col not in side_df.columns or side_df[time_col].isna().all():
        time_col = "SNAPSHOT_TIME"  # Fallback to snapshot_time if not available

    side_df["_TIME_UTC"] = pd.to_datetime(side_df[time_col])
    # Strip any timezone if present (should be naive UTC)
    if side_df["_TIME_UTC"].dt.tz is not None:
        side_df["_TIME_UTC"] = side_df["_TIME_UTC"].dt.tz_convert("UTC").dt.tz_localize(None)

    # Tip-off as naive UTC (both commence_time_utc and BOOKMAKER_LAST_UPDATE
    # are from the API, so both are in UTC — clipping works correctly)
    tipoff_utc = None
    if commence_time_utc is not None:
        tipoff_utc = pd.Timestamp(commence_time_utc)
        if tipoff_utc.tzinfo is not None:
            tipoff_utc = tipoff_utc.tz_convert("UTC").tz_localize(None)
        # Clip to 30 min pre-tipoff onward
        window_start = tipoff_utc - pd.Timedelta(minutes=30)
        clipped = side_df[side_df["_TIME_UTC"] >= window_start]
        if not clipped.empty:
            side_df = clipped

    # ── Convert UTC to naive ET for display ──
    _utc_aware = side_df["_TIME_UTC"].dt.tz_localize("UTC")
    side_df["PLOT_TIME"] = _utc_aware.dt.tz_convert(EASTERN).dt.tz_localize(None)

    # Determine Y column and formatting
    if show_implied_prob:
        y_col = "IMPLIED_PROBABILITY"
        y_title = "Implied Probability"
        hover_fmt = ".1%"
    elif market_key == "h2h":
        y_col = "OUTCOME_PRICE"
        y_title = "Moneyline"
        hover_fmt = "+d"
    else:
        y_col = "OUTCOME_POINT"
        y_title = "Spread" if market_key == "spreads" else "Total"
        hover_fmt = ".1f"

    # Build the single trace
    if selected_source == "consensus":
        plot_df = (
            side_df.groupby("PLOT_TIME")
            .agg(plot_val=(y_col, "median"))
            .reset_index()
            .sort_values("PLOT_TIME")
        )
        trace_name = "Consensus"
        trace_color = ODDS_ACCENT
    else:
        bk_df = side_df[side_df["BOOKMAKER_KEY"] == selected_source].sort_values("PLOT_TIME")
        if bk_df.empty:
            return _empty_chart(f"No data for {BOOKMAKER_DISPLAY.get(selected_source, selected_source)}")
        plot_df = bk_df.rename(columns={y_col: "plot_val"})
        trace_name = BOOKMAKER_DISPLAY.get(selected_source, selected_source.title())
        trace_color = BOOKMAKER_COLORS.get(selected_source, ODDS_ACCENT)

    fill_rgb = _hex_to_rgb(trace_color)

    # Area fill trace (ESPN win-probability style)
    fig.add_trace(
        go.Scatter(
            x=plot_df["PLOT_TIME"],
            y=plot_df["plot_val"],
            name=trace_name,
            line=dict(color=trace_color, width=2.5, shape="spline", smoothing=0.8),
            mode="lines",
            hovertemplate=f"{trace_name}: " + "%{y:" + hover_fmt + "}<extra></extra>",
            fill="tozeroy",
            fillcolor=f"rgba({fill_rgb}, 0.15)",
            fillpattern=dict(shape=""),
        )
    )

    # Tip-off vertical marker (UTC → ET)
    if tipoff_utc is not None:
        _tip_et = (
            tipoff_utc.tz_localize("UTC")
            .tz_convert(EASTERN)
            .tz_localize(None)
        )
        tipoff_str = str(_tip_et)
        fig.add_shape(
            type="line", x0=tipoff_str, x1=tipoff_str,
            y0=0, y1=1, yref="paper",
            line=dict(color=ACCENT_NBA, dash="dash", width=1),
            opacity=0.4,
        )
        fig.add_annotation(
            x=tipoff_str, y=1.02, yref="paper",
            text="TIP-OFF", showarrow=False,
            font=dict(color=ACCENT_NBA, size=9, family="Inter, sans-serif"),
            yanchor="bottom",
        )

    # "Now" or "FINAL" marker in ET
    if tipoff_utc is not None:
        if is_final:
            # Show FINAL marker at the last data point
            last_time = plot_df["PLOT_TIME"].max()
            if pd.notna(last_time):
                final_str = str(last_time)
                fig.add_shape(
                    type="line", x0=final_str, x1=final_str,
                    y0=0, y1=1, yref="paper",
                    line=dict(color=TEXT_DIMMED, dash="dash", width=1),
                    opacity=0.5,
                )
                fig.add_annotation(
                    x=final_str, y=1.02, yref="paper",
                    text="FINAL", showarrow=False,
                    font=dict(color=TEXT_DIMMED, size=9, family="Inter, sans-serif"),
                    yanchor="bottom",
                )
        else:
            now_utc = datetime.now(timezone.utc)
            if now_utc.replace(tzinfo=None) > tipoff_utc:
                _now_et = (
                    pd.Timestamp(now_utc)
                    .tz_convert(EASTERN)
                    .tz_localize(None)
                )
                now_str = str(_now_et)
                fig.add_shape(
                    type="line", x0=now_str, x1=now_str,
                    y0=0, y1=1, yref="paper",
                    line=dict(color=ACCENT_LIVE, dash="dash", width=1),
                    opacity=0.5,
                )
                fig.add_annotation(
                    x=now_str, y=1.02, yref="paper",
                    text="NOW", showarrow=False,
                    font=dict(color=ACCENT_LIVE, size=9, family="Inter, sans-serif"),
                    yanchor="bottom",
                )

    # Layout — clean, minimal, ESPN-inspired
    fig.update_layout(
        paper_bgcolor=BG_DARK,
        plot_bgcolor=BG_CARD,
        font=dict(family="Inter, sans-serif", color=TEXT_SECONDARY, size=12),
        margin=dict(l=50, r=20, t=30, b=40),
        xaxis=dict(
            gridcolor="rgba(42, 42, 62, 0.3)",
            zerolinecolor=BORDER,
            linecolor=BORDER,
            tickformat="%I:%M %p ET",
            showgrid=False,
            tickfont=dict(size=10),
        ),
        yaxis=dict(
            title=dict(text=y_title, font=dict(size=11, color=TEXT_DIMMED)),
            gridcolor="rgba(42, 42, 62, 0.3)",
            zerolinecolor="rgba(142, 197, 252, 0.2)",
            linecolor=BORDER,
            tickformat=hover_fmt if show_implied_prob else None,
            tickfont=dict(size=10),
            range=[0, 1] if show_implied_prob else None,
        ),
        showlegend=False,
        hovermode="x unified",
        height=380,
    )

    return fig


def _hex_to_rgb(hex_color: str) -> str:
    """Convert '#RRGGBB' to 'R, G, B' for CSS rgba()."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return f"{int(h[:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
    return "255, 255, 255"


def _empty_chart(message: str) -> go.Figure:
    """Return a blank chart with a centered annotation."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font=dict(size=14, color=TEXT_DIMMED),
    )
    fig.update_layout(
        paper_bgcolor=BG_DARK,
        plot_bgcolor=BG_CARD,
        font=dict(family="Inter, sans-serif", color=TEXT_SECONDARY),
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=300,
    )
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
# Bookmaker Comparison Table (HTML)
# ═══════════════════════════════════════════════════════════════════════════════


def build_bookmaker_comparison(
    odds_df: pd.DataFrame,
    event_id: str,
    market_key: str,
    home_team: str,
    away_team: str,
) -> str:
    """Build HTML table comparing all bookmakers for a game and market.

    Returns HTML string for st.markdown(..., unsafe_allow_html=True).
    """
    game_odds = odds_df[
        (odds_df["EVENT_ID"] == event_id) & (odds_df["MARKET_KEY"] == market_key)
    ]

    if game_odds.empty:
        return '<div class="stats-empty">No bookmaker data available</div>'

    # Determine sides
    if market_key == "totals":
        left_side, right_side = "Over", "Under"
        left_label, right_label = "OVER", "UNDER"
        left_logo, right_logo = "", ""
    else:
        left_side, right_side = away_team, home_team
        left_label = get_team_abbrev(away_team)
        right_label = get_team_abbrev(home_team)
        left_logo = f'<img src="{get_logo_url(away_team, 500)}" style="width:20px;height:20px;object-fit:contain;">'
        right_logo = f'<img src="{get_logo_url(home_team, 500)}" style="width:20px;height:20px;object-fit:contain;">'

    # Find best price per side (MAX = best for bettor)
    left_odds = game_odds[game_odds["SIDE"] == left_side]
    right_odds = game_odds[game_odds["SIDE"] == right_side]
    best_left = left_odds["OUTCOME_PRICE"].max() if not left_odds.empty else None
    best_right = right_odds["OUTCOME_PRICE"].max() if not right_odds.empty else None

    # Get unique bookmakers
    bookmakers = sorted(game_odds["BOOKMAKER_KEY"].unique())

    rows_html = ""
    for bk in bookmakers:
        bk_odds = game_odds[game_odds["BOOKMAKER_KEY"] == bk]
        bk_name = BOOKMAKER_DISPLAY.get(bk, bk.title())

        left_row = bk_odds[bk_odds["SIDE"] == left_side]
        right_row = bk_odds[bk_odds["SIDE"] == right_side]

        left_cell = _build_odds_cell(left_row, market_key, best_left)
        right_cell = _build_odds_cell(right_row, market_key, best_right)

        rows_html += f"""
        <div class="bk-compare-row">
            <span class="bk-col-name">{bk_name}</span>
            <div class="bk-col-side {left_cell['cls']}">{left_cell['html']}</div>
            <div class="bk-col-side {right_cell['cls']}">{right_cell['html']}</div>
        </div>"""

    # Consensus row
    consensus_left = _build_consensus_cell(left_odds)
    consensus_right = _build_consensus_cell(right_odds)

    rows_html += f"""
    <div class="bk-compare-row bk-consensus">
        <span class="bk-col-name">Consensus</span>
        <div class="bk-col-side">{consensus_left}</div>
        <div class="bk-col-side">{consensus_right}</div>
    </div>"""

    return f"""
    <div class="bk-compare-table">
        <div class="bk-compare-header">
            <span style="width:120px;">BOOKMAKER</span>
            <div class="bk-side-header">{left_logo}<span>{left_label}</span></div>
            <div class="bk-side-header">{right_logo}<span>{right_label}</span></div>
        </div>
        {rows_html}
    </div>"""


def _build_odds_cell(row_df: pd.DataFrame, market_key: str, best_price) -> dict:
    """Build a single cell for the bookmaker table. Returns dict with 'html' and 'cls'."""
    if row_df.empty:
        return {"html": '<span class="bk-col-line" style="color:#6B7280;">—</span>', "cls": ""}

    row = row_df.iloc[0]
    price = row["OUTCOME_PRICE"]
    point = row.get("OUTCOME_POINT")
    prob = row.get("IMPLIED_PROBABILITY")

    price_str = fmt_price(price)
    prob_str = fmt_prob(prob) if not _is_missing(prob) else ""

    is_best = (not _is_missing(price) and not _is_missing(best_price)
               and float(price) == float(best_price))
    cls = "bk-best-price" if is_best else ""

    if market_key == "h2h":
        html = f"""
        <span class="bk-col-line">{price_str}</span>
        <span class="bk-col-prob">{prob_str}</span>"""
    else:
        line_str = fmt_line(point)
        html = f"""
        <span class="bk-col-line">{line_str}</span>
        <span class="bk-col-price">({price_str})</span>
        <span class="bk-col-prob">{prob_str}</span>"""

    return {"html": html, "cls": cls}


def build_bookmaker_comparison_wide(
    odds_df: pd.DataFrame,
    event_id: str,
    market_key: str,
    home_team: str,
    away_team: str,
) -> str:
    """Build a transposed HTML table: 1 row per team, columns of bookmakers.

    Full-width layout designed to sit below the two-panel layout.
    Returns HTML string for st.markdown(..., unsafe_allow_html=True).
    """
    game_odds = odds_df[
        (odds_df["EVENT_ID"] == event_id) & (odds_df["MARKET_KEY"] == market_key)
    ]

    if game_odds.empty:
        return '<div class="stats-empty">No bookmaker data available</div>'

    # Determine sides
    if market_key == "totals":
        sides = [("Over", "OVER"), ("Under", "UNDER")]
    else:
        sides = [
            (away_team, get_team_abbrev(away_team)),
            (home_team, get_team_abbrev(home_team)),
        ]

    # Get unique bookmakers
    bookmakers = sorted(game_odds["BOOKMAKER_KEY"].unique())

    # Best price per side (for highlighting)
    best_price = {}
    for side_name, _ in sides:
        side_odds = game_odds[game_odds["SIDE"] == side_name]
        if not side_odds.empty:
            best_price[side_name] = side_odds["OUTCOME_PRICE"].max()

    # Build header row
    header_cells = '<th class="bkw-team-col">TEAM</th>'
    for bk in bookmakers:
        bk_short = BOOKMAKER_SHORT.get(bk, bk[:3].upper())
        header_cells += f'<th class="bkw-book-col">{bk_short}</th>'
    header_cells += '<th class="bkw-book-col bkw-consensus">CONS</th>'

    # Build data rows
    rows_html = ""
    for side_name, side_label in sides:
        side_odds_df = game_odds[game_odds["SIDE"] == side_name]
        bp = best_price.get(side_name)

        # Team cell with logo
        if market_key == "totals":
            logo_html = ""
        else:
            logo_html = (
                f'<img src="{get_logo_url(side_name, 500)}" '
                f'style="width:20px;height:20px;object-fit:contain;margin-right:6px;">'
            )

        cells = f'<td class="bkw-team-cell">{logo_html}{side_label}</td>'

        for bk in bookmakers:
            bk_row = side_odds_df[side_odds_df["BOOKMAKER_KEY"] == bk]
            if bk_row.empty:
                cells += '<td class="bkw-val-cell">—</td>'
            else:
                r = bk_row.iloc[0]
                price = r["OUTCOME_PRICE"]
                point = r.get("OUTCOME_POINT")
                is_best = (
                    not _is_missing(price)
                    and not _is_missing(bp)
                    and float(price) == float(bp)
                )
                cls = " bkw-best" if is_best else ""

                if market_key == "h2h":
                    val_str = fmt_price(price)
                else:
                    val_str = (
                        f'{fmt_line(point)}'
                        f'<span class="bkw-price">({fmt_price(price)})</span>'
                    )
                cells += f'<td class="bkw-val-cell{cls}">{val_str}</td>'

        # Consensus cell
        if not side_odds_df.empty:
            cr = side_odds_df.iloc[0]
            c_price = cr.get("CONSENSUS_PRICE")
            c_line = cr.get("CONSENSUS_LINE")
            if market_key == "h2h":
                cons_str = fmt_price(c_price)
            else:
                cons_str = (
                    f'{fmt_line(c_line)}'
                    f'<span class="bkw-price">({fmt_price(c_price)})</span>'
                )
        else:
            cons_str = "—"
        cells += f'<td class="bkw-val-cell bkw-consensus">{cons_str}</td>'

        rows_html += f'<tr>{cells}</tr>'

    return (
        f'<div class="bkw-table-wrap">'
        f'<table class="bkw-table">'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table>'
        f'</div>'
    )


def _build_consensus_cell(side_odds: pd.DataFrame) -> str:
    """Build the consensus row cell from any row (consensus is same across bookmakers)."""
    if side_odds.empty:
        return '<span class="bk-col-line" style="color:#6B7280;">—</span>'

    row = side_odds.iloc[0]
    c_price = row.get("CONSENSUS_PRICE")
    c_line = row.get("CONSENSUS_LINE")
    c_prob = row.get("CONSENSUS_IMPLIED_PROB")

    price_str = fmt_price(c_price)
    prob_str = fmt_prob(c_prob) if not _is_missing(c_prob) else ""

    if _is_missing(c_line):
        # h2h: no point, just price
        return f"""
        <span class="bk-col-line" style="color:{TEXT_PRIMARY};font-weight:700;">{price_str}</span>
        <span class="bk-col-prob">{prob_str}</span>"""
    else:
        line_str = fmt_line(c_line)
        return f"""
        <span class="bk-col-line" style="color:{TEXT_PRIMARY};font-weight:700;">{line_str}</span>
        <span class="bk-col-price">({price_str})</span>
        <span class="bk-col-prob">{prob_str}</span>"""


# ═══════════════════════════════════════════════════════════════════════════════
# Implied Probability Bar (HTML)
# ═══════════════════════════════════════════════════════════════════════════════


def build_probability_bar(
    home_team: str,
    away_team: str,
    home_prob: float,
    away_prob: float,
) -> str:
    """Build an HTML horizontal bar showing implied win probabilities.

    For spreads, these are cover probabilities. For h2h, win probabilities.
    For totals, pass home_team="Over", away_team="Under".
    """
    # Handle totals (Over/Under) which aren't real teams
    is_totals = home_team in ("Over", "Under")

    if is_totals:
        home_abbr = home_team.upper()
        away_abbr = away_team.upper()
        home_logo_html = ""
        away_logo_html = ""
    else:
        home_abbr = get_team_abbrev(home_team)
        away_abbr = get_team_abbrev(away_team)
        home_logo_html = f'<img src="{get_logo_url(home_team, 500)}" alt="">'
        away_logo_html = f'<img src="{get_logo_url(away_team, 500)}" alt="">'

    # Normalize to percentages (handle vig)
    total = home_prob + away_prob
    if total > 0:
        h_pct = home_prob / total * 100
        a_pct = away_prob / total * 100
    else:
        h_pct, a_pct = 50.0, 50.0

    return f"""
    <div class="odds-summary-card">
        <div class="odds-summary-label">IMPLIED PROBABILITY</div>
        <div class="odds-prob-bar">
            <div class="odds-prob-left" style="width:{h_pct:.1f}%;">{h_pct:.0f}%</div>
            <div class="odds-prob-right" style="width:{a_pct:.1f}%;">{a_pct:.0f}%</div>
        </div>
        <div class="odds-prob-teams">
            <div class="odds-prob-team">
                {home_logo_html}{home_abbr}
            </div>
            <div class="odds-prob-team">
                {away_abbr}{away_logo_html}
            </div>
        </div>
    </div>"""


# ═══════════════════════════════════════════════════════════════════════════════
# Summary Cards (HTML)
# ═══════════════════════════════════════════════════════════════════════════════


def build_summary_card(label: str, value: str, sub: str = "") -> str:
    """Build a single summary metric card."""
    sub_content = sub if sub else "&nbsp;"
    return f"""
    <div class="odds-summary-card">
        <div class="odds-summary-label">{label}</div>
        <div class="odds-summary-value">{value}</div>
        <div class="odds-summary-sub">{sub_content}</div>
    </div>"""


def build_movement_card(opening_val, current_val, market_key: str) -> str:
    """Build a card showing the line movement from opening to current.

    Shows direction arrow and color-codes the delta.
    """
    if _is_missing(opening_val) or _is_missing(current_val):
        return build_summary_card("MOVEMENT", "N/A", "Opening line not available")

    opening = float(opening_val)
    current = float(current_val)
    delta = current - opening

    if abs(delta) < 0.01:
        arrow = ""
        cls = "odds-movement-flat"
        delta_str = "No movement"
    elif delta > 0:
        arrow = '<span class="odds-movement-arrow">&#9650;</span>'
        cls = "odds-movement-up"
        delta_str = f"+{delta:g}"
    else:
        arrow = '<span class="odds-movement-arrow">&#9660;</span>'
        cls = "odds-movement-down"
        delta_str = f"{delta:g}"

    return f"""
    <div class="odds-summary-card">
        <div class="odds-summary-label">MOVEMENT</div>
        <div class="odds-summary-value {cls}">
            {arrow}{delta_str}
        </div>
        <div class="odds-summary-sub">
            {fmt_line(opening)} &rarr; {fmt_line(current)}
        </div>
    </div>"""
