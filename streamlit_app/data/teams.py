"""NBA team mapping: BallDontLie full_name -> abbreviation + ESPN logo URL."""

# BDL full_name -> (display abbreviation, ESPN CDN slug)
# ESPN CDN slugs verified against https://a.espncdn.com/i/teamlogos/nba/500/{slug}.png
TEAMS = {
    "Atlanta Hawks":          ("ATL", "atl"),
    "Boston Celtics":         ("BOS", "bos"),
    "Brooklyn Nets":          ("BKN", "bkn"),
    "Charlotte Hornets":      ("CHA", "cha"),
    "Chicago Bulls":          ("CHI", "chi"),
    "Cleveland Cavaliers":    ("CLE", "cle"),
    "Dallas Mavericks":       ("DAL", "dal"),
    "Denver Nuggets":         ("DEN", "den"),
    "Detroit Pistons":        ("DET", "det"),
    "Golden State Warriors":  ("GSW", "gs"),
    "Houston Rockets":        ("HOU", "hou"),
    "Indiana Pacers":         ("IND", "ind"),
    "LA Clippers":            ("LAC", "lac"),
    "Los Angeles Lakers":     ("LAL", "lal"),
    "Memphis Grizzlies":      ("MEM", "mem"),
    "Miami Heat":             ("MIA", "mia"),
    "Milwaukee Bucks":        ("MIL", "mil"),
    "Minnesota Timberwolves": ("MIN", "min"),
    "New Orleans Pelicans":   ("NOP", "no"),
    "New York Knicks":        ("NYK", "ny"),
    "Oklahoma City Thunder":  ("OKC", "okc"),
    "Orlando Magic":          ("ORL", "orl"),
    "Philadelphia 76ers":     ("PHI", "phi"),
    "Phoenix Suns":           ("PHX", "phx"),
    "Portland Trail Blazers": ("POR", "por"),
    "Sacramento Kings":       ("SAC", "sac"),
    "San Antonio Spurs":      ("SAS", "sa"),
    "Toronto Raptors":        ("TOR", "tor"),
    "Utah Jazz":              ("UTA", "utah"),
    "Washington Wizards":     ("WAS", "wsh"),
}


def get_team_abbrev(team_name: str) -> str:
    """Get 3-letter display abbreviation for a team."""
    entry = TEAMS.get(team_name)
    return entry[0] if entry else team_name[:3].upper()


def get_logo_url(team_name: str, size: int = 500) -> str:
    """Get ESPN CDN logo URL for a team. Size: 500 (large), 100 (medium), 40 (small)."""
    entry = TEAMS.get(team_name)
    slug = entry[1] if entry else "nba"
    return f"https://a.espncdn.com/i/teamlogos/nba/{size}/{slug}.png"
