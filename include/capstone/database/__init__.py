"""
Snowflake database operations for NBA Analytics pipeline.

Refactored from a single 1,537-line module into focused sub-modules:
  - connection.py: Snowflake connection + Parquet stage setup
  - cold_path.py:  Stage, merge, and teams loading (S3 → staging → production)
  - hot_path.py:   Live MERGE FROM VALUES, snapshots, cleanup
  - dq.py:         DQ runner + validation functions per dataset
  - ops.py:        Ingestion run logging + empty classification

All public functions are re-exported here for backward compatibility.
Existing imports like `from include.capstone.database import merge_games`
continue to work unchanged.
"""

# Connection
from include.capstone.database.connection import (
    get_snowflake_connection,
)

# Cold path: stage + merge
from include.capstone.database.cold_path import (
    stage_events,
    stage_odds,
    stage_games,
    stage_box_scores,
    merge_events,
    merge_odds,
    merge_games,
    merge_box_scores,
    mark_postponed_events,
    load_teams_to_snowflake,
)

# DQ validation
from include.capstone.database.dq import (
    validate_events,
    validate_odds,
    validate_games,
    validate_box_scores,
)

# Ops metadata
from include.capstone.database.ops import (
    log_ingestion_run,
    classify_empty,
)

# Hot path: live merge + cleanup
from include.capstone.database.hot_path import (
    _escape_sql,
    merge_live_scoreboard,
    merge_live_box_scores,
    merge_live_odds,
    merge_live_plays,
    snapshot_live_odds,
    cleanup_live_tables,
)

__all__ = [
    # Connection
    "get_snowflake_connection",
    # Cold path
    "stage_events",
    "stage_odds",
    "stage_games",
    "stage_box_scores",
    "merge_events",
    "merge_odds",
    "merge_games",
    "merge_box_scores",
    "mark_postponed_events",
    "load_teams_to_snowflake",
    # DQ
    "validate_events",
    "validate_odds",
    "validate_games",
    "validate_box_scores",
    # Ops
    "log_ingestion_run",
    "classify_empty",
    # Hot path
    "_escape_sql",
    "merge_live_scoreboard",
    "merge_live_box_scores",
    "merge_live_odds",
    "merge_live_plays",
    "snapshot_live_odds",
    "cleanup_live_tables",
]
