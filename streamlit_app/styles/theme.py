"""Custom CSS for game cards and NBA dashboard styling."""

# Color palette
BG_DARK = "#0C0C0C"
BG_CARD = "#1A1A2E"
BG_CARD_HOVER = "#1E1E3A"
ACCENT_NBA = "#1d428a"
ACCENT_LIVE = "#C8102E"
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#9CA3AF"
TEXT_DIMMED = "#6B7280"
BORDER = "#2A2A3E"
ODDS_ACCENT = "#8EC5FC"
GREEN = "#00A651"
STAR_COLOR = "#F59E0B"


def inject_css() -> str:
    """Return full <style> block for game card styling."""
    return f"""<style>
/* Page layout tightening (header is ~60px, need padding above that) */
.block-container {{
    padding-top: 4.5rem;
    padding-bottom: 4rem;
}}

/* ── Section headers ── */
.section-header {{
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 2.5px;
    color: {TEXT_SECONDARY};
    margin: 2rem 0 0.75rem 0;
    text-transform: uppercase;
}}
.section-header.live {{
    color: {ACCENT_LIVE};
}}

/* ── Game card ── */
.game-card {{
    background: {BG_CARD};
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 12px;
    border: 1px solid {BORDER};
    transition: border-color 0.2s, background 0.2s;
    min-height: 180px;
}}
.game-card:hover {{
    border-color: {ACCENT_NBA};
    background: {BG_CARD_HOVER};
}}
.game-card.live {{
    border-left: 3px solid {ACCENT_LIVE};
}}

/* ── Team row ── */
.team-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 0;
}}
.team-info {{
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}}
.team-logo {{
    width: 28px;
    height: 28px;
    object-fit: contain;
    flex-shrink: 0;
}}
/* Hide broken image icon when src fails to load */
.team-logo[alt=""] {{
    font-size: 0;
}}
img.team-logo:not([src]), img.team-logo[src=""] {{
    display: none;
}}
.team-abbrev {{
    font-size: 0.95rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    width: 38px;
    flex-shrink: 0;
}}
.team-name {{
    font-size: 0.8rem;
    color: {TEXT_SECONDARY};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.team-score {{
    font-size: 1.5rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    min-width: 44px;
    text-align: right;
    flex-shrink: 0;
}}
.team-score.winner {{
    color: {TEXT_PRIMARY};
}}
.team-score.loser {{
    color: {TEXT_DIMMED};
}}

/* ── Game status ── */
.game-status {{
    font-size: 0.75rem;
    color: {TEXT_SECONDARY};
    text-align: center;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid {BORDER};
}}
.game-status.live {{
    color: {ACCENT_LIVE};
    font-weight: 600;
}}

/* ── Live pulse dot ── */
.live-dot {{
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: {ACCENT_LIVE};
    margin-right: 6px;
    vertical-align: middle;
    animation: pulse 1.5s ease-in-out infinite;
}}
@keyframes pulse {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.3; }}
}}

/* ── Odds line ── */
.odds-line {{
    font-size: 0.72rem;
    color: {TEXT_SECONDARY};
    text-align: center;
    margin-top: 6px;
}}
.odds-value {{
    font-weight: 600;
    color: {ODDS_ACCENT};
}}

/* ── Result indicators ── */
.result-covered {{
    color: {GREEN} !important;
}}
.result-missed {{
    color: {ACCENT_LIVE} !important;
}}

/* ── Star rating ── */
.star-rating {{
    font-size: 0.7rem;
    color: {STAR_COLOR};
    text-align: center;
    margin-top: 3px;
}}

/* ── Sidebar branding ── */
.sidebar-brand {{
    font-size: 1.4rem;
    font-weight: 800;
    letter-spacing: 3px;
    text-align: center;
    padding: 0.75rem 0 1.25rem 0;
    color: {TEXT_PRIMARY};
}}

/* ── Page header row ── */
.page-header {{
    margin-bottom: 0;
}}
.page-header h2 {{
    margin: 0;
    font-size: 1.5rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.freshness {{
    font-size: 0.75rem;
    color: {TEXT_DIMMED};
}}
.freshness.stale {{
    color: {ACCENT_LIVE};
}}

/* ── Empty state ── */
.empty-state {{
    text-align: center;
    padding: 4rem 1rem;
    color: {TEXT_DIMMED};
}}
.empty-state h3 {{
    color: {TEXT_SECONDARY};
    margin-bottom: 0.5rem;
}}

/* ── Game detail header ── */
.gd-header {{
    max-width: 580px;
    margin: 0 auto;
    padding: 0.5rem 0 0.75rem 0;
}}
.dialog-status {{
    font-size: 0.95rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_SECONDARY};
    text-align: center;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid {BORDER};
}}
.dialog-status.live {{
    color: {ACCENT_LIVE};
}}

/* ── Scoreboard rows ── */
.gd-row {{
    display: flex;
    align-items: center;
    padding: 8px 0;
    font-variant-numeric: tabular-nums;
}}
.gd-row-head {{
    padding: 0 0 4px 0;
}}
.gd-row-head .gd-q,
.gd-row-head .gd-total {{
    font-size: 0.72rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
}}
.gd-row.loser {{
    opacity: 0.45;
}}
.gd-team-cell {{
    flex: 1;
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
}}
.gd-logo {{
    width: 36px;
    height: 36px;
    object-fit: contain;
    flex-shrink: 0;
}}
.gd-name {{
    font-size: 0.95rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.gd-row.loser .gd-name {{
    color: {TEXT_SECONDARY};
}}
.gd-q {{
    width: 36px;
    text-align: center;
    font-size: 0.88rem;
    color: {TEXT_SECONDARY};
    flex-shrink: 0;
}}
.gd-total {{
    width: 48px;
    text-align: right;
    font-size: 1.2rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    flex-shrink: 0;
}}
.gd-row.loser .gd-total {{
    color: {TEXT_SECONDARY};
}}

/* ── Play-by-Play feed ── */
.pbp-play {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 12px;
    border-bottom: 1px solid {BORDER};
    font-size: 0.82rem;
}}
.pbp-play:hover {{
    background: rgba(255, 255, 255, 0.03);
}}
.pbp-play.pbp-scoring {{
    background: rgba(0, 166, 81, 0.08);
}}
.pbp-emoji {{
    width: 20px;
    text-align: center;
    flex-shrink: 0;
    font-size: 0.85rem;
}}
.pbp-clock {{
    width: 48px;
    text-align: right;
    color: {TEXT_DIMMED};
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
}}
.pbp-indicator {{
    width: 4px;
    height: 20px;
    border-radius: 2px;
    flex-shrink: 0;
}}
.pbp-team {{
    width: 36px;
    font-weight: 700;
    color: {TEXT_SECONDARY};
    flex-shrink: 0;
    font-size: 0.75rem;
}}
.pbp-desc {{
    flex: 1;
    color: {TEXT_PRIMARY};
    min-width: 0;
}}
.pbp-score {{
    width: 160px;
    text-align: right;
    color: {ODDS_ACCENT};
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    white-space: nowrap;
}}

/* ── Period header in play-by-play ── */
.pbp-period-header {{
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    padding: 14px 10px 6px 10px;
    border-bottom: 1px solid {BORDER};
}}

/* ── Prediction tab ── */
.pred-market-toggle {{
    display: flex;
    justify-content: center;
    margin-bottom: 0.5rem;
}}

/* Center the market segmented control inside the dialog */
div[data-testid="stDialog"] [data-testid="stSegmentedControl"] {{
    max-width: 260px;
    margin: 0 auto;
}}

.pred-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    margin: 0.75rem 0 0;
}}

.pred-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 16px;
    position: relative;
    overflow: hidden;
}}
.pred-card::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, {ACCENT_NBA}, {ODDS_ACCENT});
    opacity: 0.4;
}}

.pred-card-label {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    margin-bottom: 10px;
}}

.pred-card-value {{
    font-variant-numeric: tabular-nums;
}}

/* Team side row within a card */
.pred-side {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
}}

.pred-logo {{
    width: 20px;
    height: 20px;
    object-fit: contain;
    flex-shrink: 0;
}}

.pred-team {{
    font-size: 0.78rem;
    font-weight: 700;
    color: {TEXT_SECONDARY};
    min-width: 36px;
    flex-shrink: 0;
    white-space: nowrap;
}}

.pred-line {{
    font-size: 0.88rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    font-variant-numeric: tabular-nums;
}}

/* Projection card */
.pred-projection {{
    font-size: 1.15rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    text-align: center;
    line-height: 1.4;
}}

.pred-projection-sub {{
    font-size: 0.7rem;
    color: {TEXT_DIMMED};
    text-align: center;
    margin-top: 4px;
}}

/* Projection matchup layout (with logos) */
.pred-proj-matchup {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 4px 0;
}}

.pred-proj-side {{
    display: flex;
    align-items: center;
    gap: 6px;
}}

.pred-proj-name {{
    font-size: 0.78rem;
    font-weight: 700;
    color: {TEXT_SECONDARY};
}}

.pred-proj-score {{
    font-size: 1.15rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}

.pred-proj-score.winner {{
    color: {GREEN};
}}

.pred-proj-dash {{
    font-size: 0.9rem;
    color: {TEXT_DIMMED};
    padding: 0 2px;
}}

.pred-proj-fav {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-size: 0.78rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    margin-top: 6px;
}}

.pred-proj-fav-logo {{
    width: 16px;
    height: 16px;
    object-fit: contain;
}}

/* Featured team label with logo */
.pred-feat-label {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: 0.72rem;
    color: {TEXT_DIMMED};
    margin-top: 4px;
}}

.pred-feat-logo {{
    width: 16px;
    height: 16px;
    object-fit: contain;
}}

/* Cover probability bar */
.pred-pct-main {{
    font-size: 1.3rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}

.pred-pct-bar {{
    height: 5px;
    background: {BORDER};
    border-radius: 3px;
    margin-top: 8px;
    overflow: hidden;
}}

.pred-pct-fill {{
    height: 100%;
    border-radius: 3px;
    background: linear-gradient(90deg, {ACCENT_NBA}, {ODDS_ACCENT});
    transition: width 0.4s ease;
}}

.pred-pct-fill.strong {{
    background: linear-gradient(90deg, {GREEN}, #34d058);
}}

/* Expected value */
.pred-ev {{
    font-size: 1.3rem;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
}}

.pred-ev.positive {{
    color: {GREEN};
}}

.pred-ev.negative {{
    color: {ACCENT_LIVE};
}}

.pred-ev-sub {{
    font-size: 0.7rem;
    color: {TEXT_DIMMED};
    margin-top: 4px;
}}

/* Star rating in prediction card */
.pred-stars {{
    color: {STAR_COLOR};
    font-size: 1.2rem;
    letter-spacing: 3px;
}}

.pred-stars-sub {{
    font-size: 0.7rem;
    color: {TEXT_DIMMED};
    margin-top: 4px;
}}

/* Season record */
.pred-record {{
    font-size: 1.05rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}

.pred-record-pct {{
    font-size: 0.85rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    margin-left: 6px;
}}

/* COVERED / MISSED / PUSH badges */
.pred-badge {{
    display: inline-block;
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding: 2px 7px;
    border-radius: 3px;
    margin-left: 6px;
    vertical-align: middle;
}}

.pred-badge.covered {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
}}

.pred-badge.missed {{
    background: rgba(200, 16, 46, 0.15);
    color: {ACCENT_LIVE};
}}

.pred-badge.push {{
    background: rgba(156, 163, 175, 0.15);
    color: {TEXT_SECONDARY};
}}

/* ── Team comparison bars ── */
.pred-compare {{
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid {BORDER};
}}

.pred-compare-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
}}

.pred-compare-title {{
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
}}

.pred-compare-legend {{
    display: flex;
    gap: 16px;
    font-size: 0.7rem;
    color: {TEXT_SECONDARY};
}}

.pred-legend-dot {{
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 2px;
    margin-right: 5px;
    vertical-align: middle;
}}

.pred-bar-row {{
    display: flex;
    align-items: center;
    margin-bottom: 8px;
}}

.pred-bar-label {{
    width: 80px;
    font-size: 0.72rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    text-align: right;
    padding-right: 12px;
    flex-shrink: 0;
    letter-spacing: 0.3px;
}}

.pred-bar-container {{
    flex: 1;
    display: flex;
    height: 20px;
    gap: 2px;
    align-items: center;
}}

.pred-bar-left {{
    height: 100%;
    background: {ACCENT_NBA};
    border-radius: 3px 0 0 3px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 0 8px;
    font-size: 0.68rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.9);
    font-variant-numeric: tabular-nums;
    min-width: 40px;
    transition: width 0.3s ease;
}}

.pred-bar-right {{
    height: 100%;
    background: {ACCENT_LIVE};
    border-radius: 0 3px 3px 0;
    display: flex;
    align-items: center;
    padding: 0 8px;
    font-size: 0.68rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.9);
    font-variant-numeric: tabular-nums;
    min-width: 40px;
    transition: width 0.3s ease;
}}

.pred-bar-left.advantage {{
    background: linear-gradient(90deg, {ACCENT_NBA}, #2a5cc7);
}}

.pred-bar-right.advantage {{
    background: linear-gradient(90deg, #e0243a, {ACCENT_LIVE});
}}

/* ── Matchup edge callout ── */
.pred-edge {{
    background: rgba(142, 197, 252, 0.06);
    border: 1px solid rgba(142, 197, 252, 0.15);
    border-radius: 8px;
    padding: 12px 16px;
    margin-top: 14px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
}}

.pred-edge-icon {{
    font-size: 1rem;
    flex-shrink: 0;
    line-height: 1.4;
}}

.pred-edge-body {{
    flex: 1;
}}

.pred-edge-title {{
    font-size: 0.72rem;
    font-weight: 700;
    color: {ODDS_ACCENT};
    letter-spacing: 0.5px;
    margin-bottom: 2px;
}}

.pred-edge-text {{
    font-size: 0.8rem;
    color: {TEXT_SECONDARY};
    line-height: 1.45;
}}

/* ── Prediction vs Result (Final games) ── */
.pred-result {{
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid {BORDER};
}}

.pred-result-title {{
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    margin-bottom: 12px;
}}

.pred-result-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
}}

.pred-result-box {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 12px 16px;
    text-align: center;
}}

.pred-result-label {{
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 1px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    margin-bottom: 6px;
}}

.pred-result-value {{
    font-size: 1.2rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}

.pred-result-value.positive {{
    color: {GREEN};
}}

.pred-result-value.negative {{
    color: {ACCENT_LIVE};
}}

/* ── Live game note ── */
.pred-live-note {{
    font-size: 0.72rem;
    color: {TEXT_DIMMED};
    text-align: center;
    margin-top: 6px;
    font-style: italic;
}}

/* ── Center dialog tabs ── */
[data-baseweb="tab-list"] {{
    justify-content: center !important;
}}

/* ── Detail button ── */
div[data-testid="stColumn"] div[data-testid="stButton"] {{
    margin-top: -6px;
}}
div[data-testid="stColumn"] div[data-testid="stButton"] button {{
    background: transparent;
    border: none;
    color: {TEXT_DIMMED};
    font-size: 0.55rem;
    padding: 0;
    min-height: 0;
    height: auto;
    line-height: 1;
    letter-spacing: 0.5px;
}}
div[data-testid="stColumn"] div[data-testid="stButton"] button:hover {{
    color: {TEXT_SECONDARY};
    background: transparent;
    border: none;
}}

/* ── Matchup tab ── */
.mu-section {{
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid {BORDER};
}}
.mu-section:first-child {{
    margin-top: 0;
    padding-top: 0;
    border-top: none;
}}

/* Section header with team logos on each side */
.mu-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 3rem;
    margin-bottom: 4px;
    border-bottom: 1px solid {BORDER};
}}
.mu-section-title {{
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
}}
.mu-team-badge {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.mu-team-logo {{
    width: 28px;
    height: 28px;
    object-fit: contain;
}}
.mu-team-name {{
    font-size: 0.85rem;
    font-weight: 700;
    color: {TEXT_SECONDARY};
}}

/* Comparison rows (away | label | home) */
.mu-row {{
    display: flex;
    align-items: center;
    padding: 8px 3rem;
    border-bottom: 1px solid rgba(42, 42, 62, 0.4);
}}
.mu-row:last-child {{
    border-bottom: none;
}}
.mu-label {{
    flex: 1;
    text-align: center;
    font-size: 0.75rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    letter-spacing: 0.3px;
}}
.mu-val {{
    width: 110px;
    font-size: 0.88rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    font-variant-numeric: tabular-nums;
}}
.mu-val.mu-left {{
    text-align: left;
}}
.mu-val.mu-right {{
    text-align: right;
}}
.mu-val.mu-advantage {{
    color: {GREEN};
    font-weight: 700;
}}
.mu-rank {{
    font-size: 0.65rem;
    color: {TEXT_DIMMED};
    margin-left: 4px;
}}

/* Comparison bar (inside stat rows) */
.mu-row-center {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
}}
.mu-bar {{
    width: 90%;
    display: flex;
    height: 5px;
    border-radius: 3px;
    overflow: hidden;
    gap: 2px;
}}
.mu-bar-left {{
    height: 100%;
    background: rgba(142, 197, 252, 0.25);
    border-radius: 3px 0 0 3px;
    transition: width 0.3s ease;
}}
.mu-bar-right {{
    height: 100%;
    background: rgba(142, 197, 252, 0.25);
    border-radius: 0 3px 3px 0;
    transition: width 0.3s ease;
}}
.mu-bar-left.mu-advantage {{
    background: {GREEN};
    opacity: 0.7;
}}
.mu-bar-right.mu-advantage {{
    background: {GREEN};
    opacity: 0.7;
}}

/* Sub-row for home/away splits */
.mu-sub-row {{
    display: flex;
    align-items: center;
    padding: 3px 3rem 6px 3rem;
}}
.mu-sub-label {{
    flex: 1;
    text-align: center;
    font-size: 0.65rem;
    color: {TEXT_DIMMED};
    letter-spacing: 0.3px;
}}
.mu-sub-val {{
    width: 110px;
    font-size: 0.75rem;
    color: {TEXT_DIMMED};
    font-variant-numeric: tabular-nums;
}}
.mu-sub-val.mu-left {{
    text-align: left;
}}
.mu-sub-val.mu-right {{
    text-align: right;
}}

/* Accent line under advantage row */
.mu-accent-line {{
    height: 2px;
    margin-top: 2px;
    border-radius: 1px;
}}
.mu-accent-green {{
    background: linear-gradient(90deg, {GREEN}, #34d058);
}}
.mu-accent-yellow {{
    background: linear-gradient(90deg, {STAR_COLOR}, #fbbf24);
}}

/* Category group headers within matchup stats */
.mu-group-label {{
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {ACCENT_NBA};
    text-transform: uppercase;
    padding: 10px 3rem 2px 3rem;
    margin-top: 4px;
}}

/* Rest days banner */
.mu-banner {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: rgba(142, 197, 252, 0.06);
    border: 1px solid rgba(142, 197, 252, 0.15);
    border-radius: 8px;
    padding: 10px 16px;
    margin-bottom: 12px;
}}
.mu-banner-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.78rem;
    color: {TEXT_SECONDARY};
}}
.mu-banner-item img {{
    width: 20px;
    height: 20px;
    object-fit: contain;
}}
.mu-banner-value {{
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.mu-banner-value.advantage {{
    color: {GREEN};
}}
.mu-banner-value.b2b {{
    color: {ACCENT_LIVE};
}}
.mu-banner-label {{
    font-size: 0.65rem;
    color: {TEXT_DIMMED};
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* H2H table layout */
.mu-h2h-row {{
    display: flex;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.3);
    font-size: 0.72rem;
}}
.mu-h2h-col-hdr {{
    font-size: 0.55rem;
    font-weight: 700;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 0 4px;
    border-bottom: 1px solid {BORDER};
}}
.mu-h2h-matchup {{
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
}}
.mu-h2h-teams {{
    color: {TEXT_SECONDARY};
    font-size: 0.72rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.mu-h2h-date {{
    font-size: 0.55rem;
    color: {TEXT_DIMMED};
    line-height: 1.3;
}}
.mu-h2h-col {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    flex-shrink: 0;
}}
.mu-h2h-col.su {{
    width: 70px;
}}
.mu-h2h-col.ats {{
    width: 55px;
}}
.mu-h2h-col.ou {{
    width: 45px;
}}
.mu-h2h-val {{
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    color: {TEXT_PRIMARY};
    font-size: 0.72rem;
}}
.mu-h2h-badge {{
    font-weight: 700;
    font-size: 0.55rem;
    padding: 1px 5px;
    border-radius: 2px;
    text-align: center;
    min-width: 24px;
}}
.mu-h2h-badge.win {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
}}
.mu-h2h-badge.over {{
    background: rgba(142, 197, 252, 0.15);
    color: {ODDS_ACCENT};
}}
.mu-h2h-badge.under {{
    background: rgba(156, 163, 175, 0.15);
    color: {TEXT_SECONDARY};
}}
.mu-h2h-badge.push {{
    background: rgba(156, 163, 175, 0.15);
    color: {TEXT_SECONDARY};
}}

/* Recent results — table layout */
.mu-recent-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 0;
}}
.mu-recent-header img {{
    width: 24px;
    height: 24px;
    object-fit: contain;
}}
.mu-recent-header-name {{
    font-size: 0.8rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.mu-recent-header-record {{
    font-size: 0.7rem;
    color: {TEXT_DIMMED};
    margin-left: auto;
}}
.mu-recent-row {{
    display: flex;
    align-items: center;
    padding: 5px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.3);
    font-size: 0.72rem;
}}
.mu-recent-col-hdr {{
    font-size: 0.55rem;
    font-weight: 700;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 0 4px;
    border-bottom: 1px solid {BORDER};
}}
.mu-recent-game {{
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
}}
.mu-recent-opp-name {{
    color: {TEXT_SECONDARY};
    font-size: 0.72rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.mu-recent-date {{
    font-size: 0.55rem;
    color: {TEXT_DIMMED};
    line-height: 1.3;
}}
.mu-recent-score-col {{
    display: flex;
    align-items: center;
    gap: 4px;
    width: 78px;
    flex-shrink: 0;
}}
.mu-recent-wl {{
    font-weight: 700;
    font-size: 0.65rem;
    width: 14px;
    text-align: center;
    flex-shrink: 0;
}}
.mu-recent-wl.win {{
    color: {GREEN};
}}
.mu-recent-wl.loss {{
    color: {ACCENT_LIVE};
}}
.mu-recent-score {{
    font-variant-numeric: tabular-nums;
    color: {TEXT_PRIMARY};
    font-weight: 600;
    font-size: 0.72rem;
}}
.mu-recent-ats-col {{
    width: 38px;
    text-align: center;
    flex-shrink: 0;
}}
.mu-recent-ou-col {{
    width: 38px;
    text-align: center;
    flex-shrink: 0;
}}
.mu-recent-badge {{
    font-size: 0.58rem;
    font-weight: 700;
    padding: 1px 4px;
    border-radius: 2px;
    min-width: 28px;
    text-align: center;
    display: inline-block;
}}
.mu-recent-badge.covered {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
}}
.mu-recent-badge.missed {{
    background: rgba(200, 16, 46, 0.15);
    color: {ACCENT_LIVE};
}}
.mu-recent-badge.push {{
    background: rgba(156, 163, 175, 0.15);
    color: {TEXT_SECONDARY};
}}
.mu-recent-badge.over {{
    background: rgba(142, 197, 252, 0.15);
    color: {ODDS_ACCENT};
}}
.mu-recent-badge.under {{
    background: rgba(156, 163, 175, 0.15);
    color: {TEXT_SECONDARY};
}}

/* ── Stats tab sections ── */
.stats-section {{
    margin-top: 1.25rem;
    padding-top: 1rem;
    border-top: 1px solid {BORDER};
}}
.stats-section:first-child {{
    margin-top: 0;
    padding-top: 0;
    border-top: none;
}}
.stats-section-title {{
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    margin-bottom: 12px;
}}
.stats-empty {{
    font-size: 0.82rem;
    color: {TEXT_DIMMED};
    text-align: center;
    padding: 24px 0;
}}

/* ── Odds table ── */
.odds-table {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    overflow: hidden;
    max-width: 480px;
    margin: 0 auto;
}}
.odds-table-header {{
    display: flex;
    align-items: center;
    padding: 0 0 8px 0;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 4px;
}}
.odds-table-header .odds-col-team,
.odds-table-header .odds-col {{
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
}}
.odds-table-row {{
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.3);
}}
.odds-table-row:last-of-type {{
    border-bottom: none;
}}
.odds-col-team {{
    width: 80px;
    display: flex;
    align-items: center;
    gap: 6px;
    min-width: 0;
    flex-shrink: 0;
}}
.odds-team-logo {{
    width: 24px;
    height: 24px;
    object-fit: contain;
    flex-shrink: 0;
}}
.odds-team-abbr {{
    font-size: 0.85rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    flex-shrink: 0;
}}
.odds-col {{
    flex: 1;
    text-align: center;
    font-size: 0.82rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    font-variant-numeric: tabular-nums;
}}
.odds-cell-price {{
    font-size: 0.72rem;
    color: {TEXT_DIMMED};
    font-weight: 400;
}}
.odds-cell-na {{
    color: {TEXT_DIMMED};
    font-weight: 400;
}}
.odds-source {{
    font-size: 0.65rem;
    color: {TEXT_DIMMED};
    text-align: center;
    padding-top: 8px;
    border-top: 1px solid rgba(42, 42, 62, 0.3);
    margin-top: 4px;
}}

/* ── Player box score table ── */
.box-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 0.5rem;
}}
.box-team-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0 6px 0;
    border-bottom: 1px solid {BORDER};
}}
.box-team-logo {{
    width: 22px;
    height: 22px;
    object-fit: contain;
    flex-shrink: 0;
}}
.box-team-name {{
    font-size: 0.8rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.box-team-pts {{
    font-size: 1rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}
.box-row {{
    display: flex;
    align-items: center;
    padding: 3px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.25);
    font-size: 0.68rem;
    font-variant-numeric: tabular-nums;
}}
.box-row:last-child {{
    border-bottom: none;
}}
.box-col-header {{
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    padding: 4px 0 3px 0;
    border-bottom: 1px solid {BORDER};
}}
.box-player-col {{
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: {TEXT_SECONDARY};
    font-weight: 500;
}}
.box-stat-col {{
    width: 28px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-weight: 600;
    flex-shrink: 0;
}}
.box-stat-col.box-min {{
    color: {TEXT_DIMMED};
    font-weight: 400;
}}
.box-stat-col.box-highlight {{
    color: {GREEN};
    font-weight: 700;
}}
.box-group-label {{
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: {ACCENT_NBA};
    text-transform: uppercase;
    padding: 6px 0 1px 0;
}}

/* ══════════════════════════════════════════════════════════════════════════ */
/* ── Odds page: Game selector tiles ── */
/* ══════════════════════════════════════════════════════════════════════════ */

.odds-tile {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 10px 12px;
    margin-bottom: 8px;
    text-align: center;
    transition: border-color 0.2s, background 0.2s;
}}
.odds-tile:hover {{
    border-color: {ACCENT_NBA};
    background: {BG_CARD_HOVER};
}}
.odds-tile-selected {{
    border-color: {ODDS_ACCENT} !important;
    background: rgba(142, 197, 252, 0.08) !important;
    box-shadow: 0 0 0 1px {ODDS_ACCENT};
}}
.odds-tile-teams {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
}}
.odds-tile-logo {{
    width: 24px;
    height: 24px;
    object-fit: contain;
    flex-shrink: 0;
}}
.odds-tile-abbr {{
    font-size: 0.82rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.odds-tile-at {{
    font-size: 0.68rem;
    color: {TEXT_DIMMED};
    padding: 0 2px;
}}
.odds-tile-line {{
    font-size: 0.85rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    margin-top: 4px;
    font-variant-numeric: tabular-nums;
}}
.odds-tile-status {{
    font-size: 0.65rem;
    color: {TEXT_DIMMED};
    margin-top: 2px;
}}
.odds-tile-status.live {{
    color: {ACCENT_LIVE};
    font-weight: 600;
}}

/* ── Odds page: Summary cards ── */

.odds-summary-card {{
    background: linear-gradient(135deg, {BG_CARD} 0%, rgba(29, 66, 138, 0.08) 100%);
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 18px 20px;
    position: relative;
    overflow: hidden;
}}
.odds-summary-card::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, {ACCENT_NBA}, {ODDS_ACCENT});
    opacity: 0.7;
}}
.odds-summary-label {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1.2px;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    margin-bottom: 10px;
}}
.odds-summary-value {{
    font-size: 1.5rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
}}
.odds-summary-sub {{
    font-size: 0.75rem;
    color: {TEXT_SECONDARY};
    margin-top: 6px;
}}

/* ── Movement direction indicators ── */

.odds-movement-up {{
    color: {GREEN};
}}
.odds-movement-down {{
    color: {ACCENT_LIVE};
}}
.odds-movement-flat {{
    color: {TEXT_DIMMED};
}}
.odds-movement-arrow {{
    font-size: 1rem;
    margin-right: 4px;
}}

/* ── Odds page: Bookmaker comparison table ── */

.bk-compare-table {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    overflow: hidden;
}}
.bk-compare-header {{
    display: flex;
    align-items: center;
    padding: 0 0 8px 0;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 4px;
}}
.bk-compare-header span {{
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
}}
.bk-compare-row {{
    display: flex;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.3);
}}
.bk-compare-row:last-child {{
    border-bottom: none;
}}
.bk-compare-row.bk-consensus {{
    border-top: 1px solid {BORDER};
    margin-top: 4px;
    padding-top: 10px;
}}
.bk-col-name {{
    width: 120px;
    font-size: 0.78rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    flex-shrink: 0;
}}
.bk-consensus .bk-col-name {{
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.bk-col-side {{
    flex: 1;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
}}
.bk-col-line {{
    font-size: 0.85rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    font-variant-numeric: tabular-nums;
}}
.bk-col-price {{
    font-size: 0.72rem;
    color: {TEXT_DIMMED};
    font-variant-numeric: tabular-nums;
}}
.bk-col-prob {{
    font-size: 0.65rem;
    color: {TEXT_DIMMED};
    font-variant-numeric: tabular-nums;
}}
.bk-best-price .bk-col-line {{
    color: {GREEN} !important;
}}
.bk-best-price .bk-col-price {{
    color: {GREEN} !important;
    font-weight: 600;
}}
.bk-side-header {{
    flex: 1;
    text-align: center;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
}}
.bk-side-header img {{
    width: 20px;
    height: 20px;
    object-fit: contain;
}}
.bk-side-header span {{
    font-size: 0.75rem;
    font-weight: 700;
}}

/* ── Implied probability bar (wide, Odds page) ── */

.odds-prob-bar {{
    display: flex;
    height: 36px;
    border-radius: 8px;
    overflow: hidden;
    margin: 10px 0 6px 0;
    gap: 2px;
}}
.odds-prob-left {{
    background: {ACCENT_NBA};
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 0 10px;
    font-size: 0.78rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.9);
    transition: width 0.4s ease;
    min-width: 50px;
    border-radius: 6px 0 0 6px;
}}
.odds-prob-right {{
    background: {ACCENT_LIVE};
    display: flex;
    align-items: center;
    padding: 0 10px;
    font-size: 0.78rem;
    font-weight: 700;
    color: rgba(255, 255, 255, 0.9);
    transition: width 0.4s ease;
    min-width: 50px;
    border-radius: 0 6px 6px 0;
}}
.odds-prob-teams {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4px;
}}
.odds-prob-team {{
    display: flex;
    align-items: center;
    gap: 5px;
    font-size: 0.78rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}
.odds-prob-team img {{
    width: 18px;
    height: 18px;
    object-fit: contain;
}}

/* ── Game strip (compact horizontal list of live/upcoming games) ── */

.odds-strip-item {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    text-align: center;
    cursor: pointer;
    transition: border-color 0.2s, background 0.2s;
}}
.odds-strip-item:hover {{
    border-color: {ACCENT_NBA};
    background: {BG_CARD_HOVER};
}}
.odds-strip-item.selected {{
    border-color: {ODDS_ACCENT};
    background: rgba(142, 197, 252, 0.08);
    box-shadow: 0 0 0 1px {ODDS_ACCENT};
}}
.odds-strip-teams {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    font-size: 0.75rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.odds-strip-teams img {{
    width: 18px;
    height: 18px;
    object-fit: contain;
}}
.odds-strip-line {{
    font-size: 0.78rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    margin-top: 2px;
    font-variant-numeric: tabular-nums;
}}
.odds-strip-status {{
    font-size: 0.58rem;
    color: {TEXT_DIMMED};
    margin-top: 1px;
}}
.odds-strip-status.live {{
    color: {ACCENT_LIVE};
    font-weight: 600;
}}

/* ── Odds page: Sidebar game cards ── */

.odds-sidebar-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px 14px;
    margin-bottom: 2px;
    transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
}}
.odds-sidebar-card:hover {{
    border-color: {ACCENT_NBA};
    background: {BG_CARD_HOVER};
}}
.odds-sidebar-card.selected {{
    border-color: {ODDS_ACCENT};
    background: rgba(142, 197, 252, 0.1);
    box-shadow: 0 0 0 1px {ODDS_ACCENT}, 0 0 12px rgba(142, 197, 252, 0.1);
}}
.odds-sidebar-card.live {{
    border-left: 3px solid {ACCENT_LIVE};
}}
.odds-sidebar-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 3px 0;
}}
.odds-sidebar-logo {{
    width: 24px;
    height: 24px;
    object-fit: contain;
    flex-shrink: 0;
}}
.odds-sidebar-name {{
    font-size: 0.82rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    width: 38px;
    flex-shrink: 0;
}}
.odds-sidebar-score {{
    font-size: 1rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    margin-left: auto;
    font-variant-numeric: tabular-nums;
}}
.odds-sidebar-score.loser {{
    color: {TEXT_DIMMED};
}}
.odds-sidebar-footer {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 4px;
    padding-top: 4px;
    border-top: 1px solid rgba(42, 42, 62, 0.4);
}}
.odds-sidebar-line {{
    font-size: 0.75rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    font-variant-numeric: tabular-nums;
}}
.odds-sidebar-status {{
    font-size: 0.68rem;
    color: {TEXT_DIMMED};
}}
.odds-sidebar-status.live {{
    color: {ACCENT_LIVE};
    font-weight: 600;
}}
.odds-sidebar-best {{
    font-size: 0.72rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    margin-left: auto;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}
.odds-sidebar-bk {{
    font-size: 0.6rem;
    font-weight: 700;
    color: {TEXT_DIMMED};
    margin-left: 3px;
}}

/* ── Game detail header for odds page ── */

.odds-game-header {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 20px;
    padding: 16px 0;
    margin-bottom: 12px;
    border-bottom: 1px solid {BORDER};
}}
.odds-game-header img {{
    width: 44px;
    height: 44px;
    object-fit: contain;
}}
.odds-game-header-team {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.odds-game-header-name {{
    font-size: 1.1rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.odds-game-header-vs {{
    font-size: 0.85rem;
    color: {TEXT_DIMMED};
}}
.odds-game-header-score {{
    font-size: 1.5rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    min-width: 40px;
    text-align: center;
}}

/* ── Bookmaker comparison: transposed wide table ── */

.bkw-table-wrap {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 12px 16px;
    overflow-x: auto;
}}
.bkw-table {{
    width: 100%;
    border-collapse: collapse;
    border-spacing: 0;
    font-family: Inter, system-ui, sans-serif;
}}
.bkw-table tr,
.bkw-table td,
.bkw-table th {{
    border: none !important;
}}
.bkw-table thead tr {{
    border-bottom: 1px solid {BORDER} !important;
}}
.bkw-table th {{
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    padding: 0 0 8px 0;
    text-align: center;
    white-space: nowrap;
}}
.bkw-team-col {{
    text-align: left !important;
    width: 90px;
}}
.bkw-book-col {{
    min-width: 70px;
}}
.bkw-team-cell {{
    display: flex;
    align-items: center;
    font-size: 0.82rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    padding: 8px 0;
    white-space: nowrap;
}}
.bkw-val-cell {{
    text-align: center;
    font-size: 0.82rem;
    font-weight: 600;
    color: {ODDS_ACCENT};
    padding: 8px 4px;
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
}}
.bkw-val-cell.bkw-best {{
    color: {GREEN} !important;
}}
.bkw-val-cell.bkw-best .bkw-price {{
    color: {GREEN} !important;
}}
.bkw-val-cell.bkw-consensus {{
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.bkw-price {{
    font-size: 0.68rem;
    color: {TEXT_DIMMED};
    margin-left: 2px;
}}

/* ══════════════════════════════════════════════════════════════════════════ */
/* ── Predictions page: Best Bets Strip ── */
/* ══════════════════════════════════════════════════════════════════════════ */

.best-bets-strip {{
    margin-bottom: 1rem;
    text-align: center;
}}

.best-bets-header {{
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 2px;
    color: {TEXT_SECONDARY};
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}}

.best-bets-tiles {{
    display: flex;
    gap: 12px;
    justify-content: center;
}}

.best-bet-tile {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 20px;
    min-width: 160px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s, transform 0.2s;
}}

.best-bet-tile::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, {STAR_COLOR}, #fbbf24);
}}

.best-bet-tile:hover {{
    border-color: {STAR_COLOR};
    transform: translateY(-2px);
}}

.best-bet-matchup {{
    font-size: 0.7rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    letter-spacing: 0.5px;
    margin-bottom: 6px;
}}

.best-bet-pick {{
    font-size: 1rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    margin-bottom: 4px;
}}

.best-bet-stars {{
    font-size: 0.9rem;
    color: {STAR_COLOR};
    letter-spacing: 2px;
    margin-bottom: 4px;
}}

.best-bet-ev {{
    font-size: 0.85rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}}

.best-bet-ev.ev-positive {{
    color: {GREEN};
}}

.best-bet-ev.ev-negative {{
    color: {ACCENT_LIVE};
}}

.best-bet-ev.ev-neutral {{
    color: {TEXT_DIMMED};
}}

/* ══════════════════════════════════════════════════════════════════════════ */
/* ── Predictions page: Main Table ── */
/* ══════════════════════════════════════════════════════════════════════════ */

.pred-table-wrap {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    overflow: hidden;
}}

.pred-table {{
    width: 100%;
    border-collapse: collapse;
    font-family: Inter, system-ui, sans-serif;
}}

.pred-table thead tr {{
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid {BORDER};
}}

.pred-table th {{
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    padding: 12px 10px;
    text-align: left;
    white-space: nowrap;
}}

.pred-th-time {{
    width: 80px;
}}

.pred-th-matchup {{
    width: 180px;
}}

.pred-th-spread,
.pred-th-total {{
    width: 130px;
}}

.pred-th-ev {{
    width: 70px;
    text-align: center !important;
}}

.pred-th-ml {{
    width: 100px;
    text-align: center !important;
}}

.pred-th-proj {{
    width: 70px;
    text-align: center !important;
}}

.pred-th-best {{
    width: 120px;
}}

.pred-row {{
    border-bottom: 1px solid rgba(42, 42, 62, 0.4);
    transition: background 0.15s;
}}

.pred-row:hover {{
    background: rgba(255, 255, 255, 0.02);
}}

.pred-row:last-child {{
    border-bottom: none;
}}

.pred-row-live {{
    background: rgba(200, 16, 46, 0.05);
}}

.pred-row-live:hover {{
    background: rgba(200, 16, 46, 0.08);
}}

.pred-table td {{
    padding: 12px 10px;
    font-size: 0.82rem;
    color: {TEXT_PRIMARY};
    vertical-align: middle;
}}

.pred-td-time {{
    font-weight: 600;
    color: {TEXT_SECONDARY};
    font-variant-numeric: tabular-nums;
}}

.pred-live-indicator {{
    color: {ACCENT_LIVE};
    font-weight: 600;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    gap: 4px;
}}

.pred-matchup {{
    display: flex;
    align-items: center;
    gap: 6px;
}}

.pred-team-logo {{
    width: 22px;
    height: 22px;
    object-fit: contain;
    flex-shrink: 0;
}}

.pred-team-abbr {{
    font-weight: 700;
    font-size: 0.85rem;
}}

.pred-at {{
    color: {TEXT_DIMMED};
    font-size: 0.72rem;
    padding: 0 2px;
}}

.pred-td-spread,
.pred-td-total {{
    font-weight: 600;
    color: {ODDS_ACCENT};
    font-variant-numeric: tabular-nums;
}}

.pred-price {{
    font-size: 0.72rem;
    font-weight: 400;
    color: {TEXT_DIMMED};
    margin-left: 2px;
}}

.pred-td-ev {{
    text-align: center;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
}}

.pred-td-ev.ev-positive {{
    color: {GREEN};
}}

.pred-td-ev.ev-negative {{
    color: {ACCENT_LIVE};
}}

.pred-td-ev.ev-neutral {{
    color: {TEXT_DIMMED};
}}

.pred-td-ml {{
    text-align: center;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    font-variant-numeric: tabular-nums;
}}

.pred-td-proj {{
    text-align: center;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    font-variant-numeric: tabular-nums;
}}

.pred-td-best {{
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}

.pred-best-stars {{
    color: {STAR_COLOR};
    font-size: 0.78rem;
    letter-spacing: 1px;
    margin-left: 4px;
}}

.pred-empty {{
    text-align: center;
    padding: 3rem 1rem;
    color: {TEXT_DIMMED};
    font-size: 0.9rem;
}}

/* ── Predictions page: Detail expansion ── */

.pred-detail {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 20px;
    margin-top: 8px;
}}

.pred-detail-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 10px;
    border-bottom: 1px solid {BORDER};
}}

.pred-detail-team {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}

.pred-detail-logo {{
    width: 24px;
    height: 24px;
    object-fit: contain;
}}

.pred-detail-title {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
}}

.pred-detail-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.3);
}}

.pred-detail-row:last-child {{
    border-bottom: none;
}}

.pred-detail-val {{
    width: 60px;
    font-size: 0.88rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    font-variant-numeric: tabular-nums;
}}

.pred-detail-val:first-child {{
    text-align: left;
}}

.pred-detail-val:last-child {{
    text-align: right;
}}

.pred-detail-val.pred-advantage {{
    color: {GREEN};
    font-weight: 700;
}}

.pred-detail-label {{
    flex: 1;
    text-align: center;
    font-size: 0.72rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    letter-spacing: 0.3px;
}}

/* ── Predictions page: Filters row ── */

.pred-filters {{
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 1rem;
    padding: 10px 0;
}}

.pred-filter-label {{
    font-size: 0.72rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    letter-spacing: 0.5px;
}}

/* ── Predictions page: Score Projection ── */

.pred-score-projection {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
}}

.pred-section-label {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
    margin-bottom: 12px;
}}

.pred-proj-matchup {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
}}

.pred-proj-team {{
    display: flex;
    align-items: center;
    gap: 8px;
}}

.pred-proj-logo {{
    width: 32px;
    height: 32px;
    object-fit: contain;
}}

.pred-proj-abbr {{
    font-size: 0.9rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}

.pred-proj-score {{
    font-size: 1.5rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}

.pred-proj-score.winner {{
    color: {GREEN};
}}

.pred-proj-sep {{
    font-size: 1.2rem;
    color: {TEXT_DIMMED};
    margin: 0 4px;
}}

.pred-proj-sub {{
    text-align: center;
    font-size: 0.75rem;
    color: {TEXT_DIMMED};
    margin-top: 8px;
}}

/* ── Predictions page: Multi-market grid ── */

.pred-markets-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 12px;
}}

.pred-market-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 16px;
    position: relative;
    overflow: hidden;
}}

.pred-market-card::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, {ACCENT_NBA}, {ODDS_ACCENT});
    opacity: 0.4;
}}

.pred-market-title {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
    text-align: center;
    margin-bottom: 10px;
}}

.pred-market-lines {{
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid {BORDER};
}}

.pred-market-side {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
}}

.pred-market-logo {{
    width: 20px;
    height: 20px;
    object-fit: contain;
}}

.pred-market-icon {{
    width: 20px;
}}

.pred-market-team {{
    font-size: 0.8rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    flex: 1;
}}

.pred-market-line {{
    font-size: 0.8rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}

.pred-no-data {{
    font-size: 0.8rem;
    color: {TEXT_DIMMED};
    text-align: center;
    padding: 20px 0;
}}

/* ── Market card stats ── */

.pred-market-stats {{
    display: flex;
    flex-direction: column;
    gap: 6px;
}}

.pred-stat-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
}}

.pred-stat-label {{
    font-size: 0.68rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    letter-spacing: 0.3px;
}}

.pred-stat-value {{
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
}}

.pred-stat-num {{
    font-size: 0.85rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
}}

.pred-stat-bar {{
    width: 60px;
    height: 4px;
    background: {BORDER};
    border-radius: 2px;
    overflow: hidden;
}}

.pred-stat-bar-fill {{
    height: 100%;
    background: {ODDS_ACCENT};
    border-radius: 2px;
    transition: width 0.3s ease;
}}

.pred-stat-bar-fill.strong {{
    background: {GREEN};
}}

.pred-stat-ev {{
    font-size: 0.85rem;
    font-weight: 700;
}}

.pred-stat-ev.positive {{
    color: {GREEN};
}}

.pred-stat-ev.negative {{
    color: {ACCENT_LIVE};
}}

.pred-stars {{
    font-size: 0.85rem;
    color: {STAR_COLOR};
    letter-spacing: 1px;
}}

.pred-stat-record {{
    font-size: 0.75rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    display: flex;
    align-items: center;
    gap: 4px;
}}

.pred-stat-logo {{
    width: 14px;
    height: 14px;
    object-fit: contain;
}}

/* ── Compact edge indicator ── */

.pred-edge {{
    font-size: 0.68rem;
    font-weight: 600;
    text-align: center;
    padding: 6px 10px;
    border-radius: 6px;
    margin-top: 10px;
}}

.pred-edge.edge-positive {{
    background: rgba(0, 166, 81, 0.12);
    color: {GREEN};
}}

.pred-edge.edge-slight {{
    background: rgba(142, 197, 252, 0.1);
    color: {ODDS_ACCENT};
}}

.pred-edge.edge-negative {{
    background: rgba(200, 16, 46, 0.08);
    color: {TEXT_DIMMED};
}}

.pred-edge.edge-neutral {{
    background: rgba(156, 163, 175, 0.08);
    color: {TEXT_DIMMED};
}}

/* ── L10 Team Comparison ── */

.pred-compare {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 10px;
    padding: 14px 16px;
    margin-top: 12px;
}}

.pred-compare-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
}}

.pred-compare-title {{
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIMMED};
}}

.pred-compare-legend {{
    display: flex;
    gap: 12px;
}}

.pred-legend-item {{
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    color: {TEXT_SECONDARY};
}}

.pred-legend-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
}}

.pred-legend-dot.home {{
    background: #1d428a;
}}

.pred-legend-dot.away {{
    background: #C8102E;
}}

.pred-bar-row {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
}}

.pred-bar-label {{
    font-size: 0.7rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    width: 50px;
}}

.pred-bar-track {{
    flex: 1;
    display: flex;
    height: 20px;
    border-radius: 4px;
    overflow: hidden;
}}

.pred-bar-home {{
    background: #1d428a;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 600;
    color: white;
    min-width: 40px;
}}

.pred-bar-away {{
    background: #C8102E;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.7rem;
    font-weight: 600;
    color: white;
    min-width: 40px;
}}

.pred-bar-home.advantage {{
    background: #1d428a;
    box-shadow: inset 0 0 0 2px {GREEN};
}}

.pred-bar-away.advantage {{
    background: #C8102E;
    box-shadow: inset 0 0 0 2px {GREEN};
}}

.pred-live-note {{
    text-align: center;
    font-size: 0.75rem;
    font-style: italic;
    color: {TEXT_DIMMED};
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid {BORDER};
}}

/* ── Predictions card: Compact horizontal layout ── */

.pred-compact-row {{
    display: flex;
    align-items: stretch;
    gap: 8px;
}}

.pred-teams {{
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 2px;
    min-width: 70px;
}}

.pred-team-row {{
    display: flex;
    align-items: center;
    gap: 4px;
}}

.pred-team-logo {{
    width: 16px;
    height: 16px;
    object-fit: contain;
}}

.pred-team-name {{
    font-size: 0.75rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    min-width: 28px;
}}

.pred-score {{
    font-size: 0.75rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    margin-left: auto;
    font-variant-numeric: tabular-nums;
}}

.pred-score.loser {{
    color: {TEXT_DIMMED};
}}

.pred-mkts {{
    display: flex;
    flex: 1;
    gap: 4px;
}}

.pred-mkt {{
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 4px 2px;
    background: rgba(42, 42, 62, 0.4);
    border-radius: 4px;
}}

.pred-mkt.has-value {{
    background: rgba(0, 166, 81, 0.12);
}}

.pred-mkt-lbl {{
    font-size: 0.55rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
    letter-spacing: 0.3px;
}}

.pred-mkt-val {{
    font-size: 0.7rem;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
}}

.pred-mkt.has-value .pred-mkt-val {{
    color: {GREEN};
}}

.pred-mkt-stars {{
    font-size: 0.5rem;
    color: {STAR_COLOR};
    line-height: 1;
    min-height: 8px;
}}

.pred-compact-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 4px;
    margin-top: 4px;
    border-top: 1px solid {BORDER};
    font-size: 0.7rem;
}}

/* ══════════════════════════════════════════════════════════════════════════ */
/* ── Grades page ── */
/* ══════════════════════════════════════════════════════════════════════════ */

/* ── Grade card (one per game) ── */
.grade-card {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 14px;
    transition: border-color 0.2s, background 0.2s;
    height: 100%;
    box-sizing: border-box;
}}
.grade-card:hover {{
    border-color: {ACCENT_NBA};
    background: {BG_CARD_HOVER};
}}

/* ── Matchup header row ── */
.grade-matchup {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    padding-bottom: 14px;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 14px;
}}
.grade-matchup-team {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.grade-matchup-logo {{
    width: 32px;
    height: 32px;
    object-fit: contain;
    flex-shrink: 0;
}}
.grade-matchup-name {{
    font-size: 0.9rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
}}
.grade-matchup-score {{
    font-size: 1.3rem;
    font-weight: 800;
    color: {TEXT_PRIMARY};
    font-variant-numeric: tabular-nums;
    min-width: 36px;
    text-align: center;
}}
.grade-matchup-score.winner {{
    color: {TEXT_PRIMARY};
}}
.grade-matchup-score.loser {{
    color: {TEXT_DIMMED};
}}
.grade-matchup-vs {{
    font-size: 0.75rem;
    color: {TEXT_DIMMED};
    padding: 0 2px;
}}
.grade-matchup-result {{
    display: inline-block;
    font-size: 0.58rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    padding: 2px 7px;
    border-radius: 3px;
    margin-left: 8px;
    vertical-align: middle;
}}
.grade-matchup-result.covered {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
}}
.grade-matchup-result.missed {{
    background: rgba(200, 16, 46, 0.15);
    color: {ACCENT_LIVE};
}}
.grade-matchup-result.push {{
    background: rgba(156, 163, 175, 0.15);
    color: {TEXT_SECONDARY};
}}

/* ── Grade columns (home / away side by side) ── */
.grade-cols {{
    display: flex;
    gap: 16px;
}}
.grade-team-col {{
    flex: 1;
    min-width: 0;
}}
.grade-team-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}}
.grade-team-header img {{
    width: 22px;
    height: 22px;
    object-fit: contain;
}}
.grade-team-header-name {{
    font-size: 0.8rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    flex: 1;
}}
.grade-team-header-score {{
    font-size: 0.95rem;
    font-weight: 700;
    color: {TEXT_SECONDARY};
    font-variant-numeric: tabular-nums;
}}

/* ── Grade badge (large) ── */
.grade-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 52px;
    height: 52px;
    border-radius: 10px;
    font-size: 1.3rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    flex-shrink: 0;
}}
.grade-badge.grade-a-plus {{
    background: rgba(0, 200, 83, 0.15);
    color: #00C853;
    border: 1px solid rgba(0, 200, 83, 0.3);
}}
.grade-badge.grade-a {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
    border: 1px solid rgba(0, 166, 81, 0.3);
}}
.grade-badge.grade-b {{
    background: rgba(142, 197, 252, 0.15);
    color: {ODDS_ACCENT};
    border: 1px solid rgba(142, 197, 252, 0.3);
}}
.grade-badge.grade-c {{
    background: rgba(245, 158, 11, 0.15);
    color: {STAR_COLOR};
    border: 1px solid rgba(245, 158, 11, 0.3);
}}
.grade-badge.grade-d {{
    background: rgba(255, 109, 0, 0.15);
    color: #FF6D00;
    border: 1px solid rgba(255, 109, 0, 0.3);
}}
.grade-badge.grade-f {{
    background: rgba(200, 16, 46, 0.15);
    color: {ACCENT_LIVE};
    border: 1px solid rgba(200, 16, 46, 0.3);
}}

/* ── Small grade badge (off/def, player rows) ── */
.grade-small-badge {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 30px;
    height: 22px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: -0.3px;
    padding: 0 5px;
}}
.grade-small-badge.grade-a-plus {{
    background: rgba(0, 200, 83, 0.15);
    color: #00C853;
}}
.grade-small-badge.grade-a {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
}}
.grade-small-badge.grade-b {{
    background: rgba(142, 197, 252, 0.15);
    color: {ODDS_ACCENT};
}}
.grade-small-badge.grade-c {{
    background: rgba(245, 158, 11, 0.15);
    color: {STAR_COLOR};
}}
.grade-small-badge.grade-d {{
    background: rgba(255, 109, 0, 0.15);
    color: #FF6D00;
}}
.grade-small-badge.grade-f {{
    background: rgba(200, 16, 46, 0.15);
    color: {ACCENT_LIVE};
}}

/* ── Grade row: overall grade + off/def breakdown ── */
.grade-overview {{
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 14px;
}}
.grade-sub-grades {{
    display: flex;
    flex-direction: column;
    gap: 4px;
}}
.grade-sub-row {{
    display: flex;
    align-items: center;
    gap: 6px;
}}
.grade-sub-label {{
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
    width: 28px;
}}

/* ── Stat table (aligned like player grades) ── */
.grade-stats {{
    border-top: 1px solid rgba(42, 42, 62, 0.4);
    padding-top: 6px;
}}
.grade-stat-col-hdr {{
    display: flex;
    align-items: center;
    padding: 4px 0 3px 0;
    border-bottom: 1px solid {BORDER};
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
}}
.grade-stat-row {{
    display: flex;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.25);
    font-variant-numeric: tabular-nums;
}}
.grade-stat-row:last-child {{
    border-bottom: none;
}}
.grade-stat-label {{
    flex: 1;
    min-width: 0;
    font-weight: 600;
    color: {TEXT_SECONDARY};
    font-size: 0.7rem;
    letter-spacing: 0.3px;
}}
.grade-stat-actual {{
    width: 42px;
    text-align: center;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-size: 0.7rem;
    flex-shrink: 0;
}}
.grade-stat-avg {{
    width: 42px;
    text-align: center;
    font-weight: 400;
    color: {TEXT_DIMMED};
    font-size: 0.7rem;
    flex-shrink: 0;
}}
.grade-stat-delta {{
    width: 46px;
    text-align: center;
    font-weight: 700;
    font-size: 0.7rem;
    flex-shrink: 0;
}}
.grade-stat-delta.positive {{
    color: {GREEN};
}}
.grade-stat-delta.negative {{
    color: {ACCENT_LIVE};
}}
.grade-stat-delta.neutral {{
    color: {TEXT_DIMMED};
}}

/* ── Flex wrapper so both columns match height ── */
.grade-row {{
    display: flex;
    align-items: stretch;
    gap: 16px;
}}
.grade-row > * {{
    flex: 1;
    min-width: 0;
}}

/* ── Key takeaways panel ── */
.grade-takeaway-panel {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 16px 18px;
    margin-bottom: 14px;
    display: flex;
    flex-direction: column;
    height: 100%;
    box-sizing: border-box;
}}
.grade-takeaway-team {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid {BORDER};
}}
.grade-takeaway-team img {{
    width: 20px;
    height: 20px;
    object-fit: contain;
}}
.grade-takeaway-team-name {{
    font-size: 0.78rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    flex: 1;
}}
.grade-takeaway-item {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 10px;
    margin: 4px 0;
    border-radius: 6px;
    border-left: 3px solid transparent;
}}
.grade-takeaway-item.tk-good {{
    background: rgba(0, 166, 81, 0.06);
    border-left-color: {GREEN};
}}
.grade-takeaway-item.tk-bad {{
    background: rgba(200, 16, 46, 0.06);
    border-left-color: {ACCENT_LIVE};
}}
.grade-takeaway-arrow {{
    font-size: 0.7rem;
    font-weight: 800;
    flex-shrink: 0;
    width: 14px;
    text-align: center;
    line-height: 1;
}}
.grade-takeaway-arrow.tk-up {{
    color: {GREEN};
}}
.grade-takeaway-arrow.tk-down {{
    color: {ACCENT_LIVE};
}}
.grade-takeaway-body {{
    flex: 1;
    min-width: 0;
}}
.grade-takeaway-stat {{
    font-size: 0.72rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    line-height: 1.3;
}}
.grade-takeaway-desc {{
    font-size: 0.65rem;
    color: {TEXT_DIMMED};
    line-height: 1.3;
    margin-top: 1px;
}}
.grade-takeaway-pill {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    flex-shrink: 0;
    letter-spacing: -0.2px;
}}
.grade-takeaway-pill.tk-good-pill {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
}}
.grade-takeaway-pill.tk-bad-pill {{
    background: rgba(200, 16, 46, 0.15);
    color: {ACCENT_LIVE};
}}
.grade-takeaway-divider {{
    height: 1px;
    background: {BORDER};
    margin: 10px 0;
}}

/* ── Spread result pill in team header ── */
.grade-spread-pill {{
    display: inline-block;
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    padding: 1px 6px;
    border-radius: 3px;
    margin-left: auto;
}}
.grade-spread-pill.covered {{
    background: rgba(0, 166, 81, 0.15);
    color: {GREEN};
}}
.grade-spread-pill.missed {{
    background: rgba(200, 16, 46, 0.15);
    color: {ACCENT_LIVE};
}}
.grade-spread-pill.push {{
    background: rgba(156, 163, 175, 0.15);
    color: {TEXT_SECONDARY};
}}

/* ── Player grades table ── */
.grade-player-table {{
    width: 100%;
    font-size: 0.7rem;
}}
.grade-player-col-hdr {{
    display: flex;
    align-items: center;
    padding: 4px 0 3px 0;
    border-bottom: 1px solid {BORDER};
    font-size: 0.55rem;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: {TEXT_DIMMED};
    text-transform: uppercase;
}}
.grade-player-row {{
    display: flex;
    align-items: center;
    padding: 4px 0;
    border-bottom: 1px solid rgba(42, 42, 62, 0.25);
    font-variant-numeric: tabular-nums;
}}
.grade-player-row:last-child {{
    border-bottom: none;
}}
.grade-player-name {{
    flex: 1;
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    color: {TEXT_SECONDARY};
    font-weight: 500;
    font-size: 0.7rem;
}}
.grade-player-stat {{
    width: 32px;
    text-align: center;
    color: {TEXT_PRIMARY};
    font-weight: 600;
    flex-shrink: 0;
    font-size: 0.7rem;
}}
.grade-player-stat.dimmed {{
    color: {TEXT_DIMMED};
    font-weight: 400;
}}
.grade-player-gs {{
    width: 38px;
    text-align: center;
    font-weight: 700;
    flex-shrink: 0;
    font-size: 0.72rem;
}}
.grade-player-gs.positive {{
    color: {GREEN};
}}
.grade-player-gs.negative {{
    color: {ACCENT_LIVE};
}}
.grade-player-gs.neutral {{
    color: {TEXT_PRIMARY};
}}
.grade-player-grade {{
    width: 32px;
    text-align: center;
    flex-shrink: 0;
}}
.grade-player-delta {{
    width: 38px;
    text-align: center;
    font-weight: 600;
    flex-shrink: 0;
    font-size: 0.65rem;
}}
.grade-player-delta.positive {{
    color: {GREEN};
}}
.grade-player-delta.negative {{
    color: {ACCENT_LIVE};
}}
.grade-player-delta.neutral {{
    color: {TEXT_DIMMED};
}}

/* ── Player team header inside expander ── */
.grade-player-team-hdr {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 0 6px 0;
    border-bottom: 1px solid {BORDER};
    margin-bottom: 2px;
}}
.grade-player-team-hdr img {{
    width: 22px;
    height: 22px;
    object-fit: contain;
}}
.grade-player-team-hdr-name {{
    font-size: 0.8rem;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    flex: 1;
}}

/* ── Divider between home/away in grade cols ── */
.grade-divider {{
    width: 1px;
    background: {BORDER};
    flex-shrink: 0;
}}

/* ── Rest days banner (prediction detail) ── */
.pred-rest-bar {{
    display: flex;
    justify-content: center;
    gap: 12px;
    margin: 10px 0 14px 0;
}}
.pred-rest-team {{
    display: flex;
    align-items: center;
    gap: 6px;
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 12px;
    background: {BG_CARD};
}}
.pred-rest-team.rest-b2b {{
    border-color: rgba(200, 16, 46, 0.4);
}}
.pred-rest-team.rest-rested {{
    border-color: rgba(0, 166, 81, 0.4);
}}
.pred-rest-label {{
    font-size: 0.72rem;
    font-weight: 700;
    color: {TEXT_SECONDARY};
}}
.pred-rest-value {{
    font-size: 0.72rem;
    font-weight: 600;
    color: {TEXT_DIMMED};
}}
.pred-rest-team.rest-b2b .pred-rest-value {{
    color: {ACCENT_LIVE};
}}
.pred-rest-team.rest-rested .pred-rest-value {{
    color: {GREEN};
}}

/* ── Sub-header divider in matchup (Four Factors / Pace) ── */
.mu-sub-header {{
    font-size: 0.6rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {ACCENT_NBA};
    text-transform: uppercase;
    text-align: center;
    padding: 10px 3rem 4px 3rem;
    margin-top: 2px;
    border-top: 1px solid rgba(42, 42, 62, 0.4);
}}
</style>"""
